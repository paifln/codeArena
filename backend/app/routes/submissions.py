from ..services.submission_queue import enqueue_submission
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, or_
from sqlalchemy.orm import Session as DBSession
from ..db import get_db, lock_write
from ..models import (
    Contest,
    Problem,
    Submission,
    SubmissionTestResult,
    User,
)
from .. import schemas as S
from ..security import current_user, teacher, owned
from ..services.access import team_id_for
from ..services import access_contest, audit, iso, judge_status, manager

router = APIRouter()


def submission_public(db, s, u, detail=False):
    c = db.get(Contest, s.contest_id)
    privileged = manager(c, u)
    teammate = s.team_id is not None and s.team_id == team_id_for(db, c.id, u.id)
    if not privileged and s.user_id != u.id and not teammate:
        raise HTTPException(404, "Submission not found")
    data = {
        k: getattr(s, k)
        for k in (
            "id",
            "user_id",
            "problem_id",
            "contest_id",
            "kind",
            "language",
            "team_id",
            "is_practice",
            "score",
            "feedback",
            "status",
            "time_ms",
            "memory_kb",
        )
    }
    data.update(
        created_at=iso(s.created_at),
        finished_at=iso(s.finished_at),
        problem_title=db.get(Problem, s.problem_id).title,
        user_name=db.get(User, s.user_id).name,
    )
    if detail:
        data["source"] = s.source
        data["error"] = (
            s.error
            if privileged or s.kind == "RUN" or s.status == "COMPILATION_ERROR"
            else (
                "Judge infrastructure error; ask your teacher to retry."
                if s.status == "SYSTEM_ERROR"
                else ""
            )
        )
        results = db.scalars(
            select(SubmissionTestResult)
            .where(SubmissionTestResult.submission_id == s.id)
            .order_by(SubmissionTestResult.ordinal)
        ).all()
        data["tests"] = [
            {
                "ordinal": r.ordinal,
                "verdict": r.verdict,
                "time_ms": r.time_ms,
                "memory_kb": r.memory_kb,
                "stdout": r.stdout,
                "stderr": r.stderr,
                "is_sample": r.is_sample,
            }
            for r in results
            if privileged
            or (s.kind == "RUN" and (r.is_sample or s.custom_input is not None))
        ]
        if privileged:
            data["history"] = s.history
            from ..services.code_review import comment_review

            data["code_review"] = comment_review(s.source, s.language)
    return data


@router.post("/submissions", status_code=202)
def submit(
    req: S.SubmitIn, user=Depends(current_user), db: DBSession = Depends(get_db)
):
    return submission_public(db, enqueue_submission(db, req, user), user)


@router.get("/submissions")
def submissions(
    contest_id: int | None = None,
    problem_id: int | None = None,
    status: str | None = None,
    team_id: int | None = None,
    language: str | None = None,
    after: float | None = None,
    before: float | None = None,
    offset: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    user=Depends(current_user),
    db: DBSession = Depends(get_db),
):
    q = select(Submission)
    if contest_id:
        c = access_contest(db, contest_id, user)
        q = q.where(Submission.contest_id == c.id)
        if not manager(c, user):
            q = q.where(
                or_(
                    Submission.user_id == user.id,
                    Submission.team_id == (team_id_for(db, c.id, user.id) or -1),
                )
            )
    elif user.role == "STUDENT":
        q = q.where(Submission.user_id == user.id)
    elif user.role == "TEACHER":
        q = q.where(
            Submission.contest_id.in_(
                select(Contest.id).where(Contest.author_id == user.id)
            )
        )
    if team_id:
        q = q.where(Submission.team_id == team_id)
    if language:
        q = q.where(Submission.language == language)
    if after is not None:
        q = q.where(Submission.created_at >= after)
    if before is not None:
        q = q.where(Submission.created_at <= before)
    if problem_id:
        q = q.where(Submission.problem_id == problem_id)
    if status:
        q = q.where(Submission.status == status)
    return [
        submission_public(db, s, user)
        for s in db.scalars(
            q.order_by(Submission.created_at.desc(), Submission.id.desc())
            .offset(offset)
            .limit(limit)
        )
    ]


@router.get("/submissions/{sid}")
def submission_detail(
    sid: int, user=Depends(current_user), db: DBSession = Depends(get_db)
):
    s = db.get(Submission, sid)
    if not s:
        raise HTTPException(404, "Submission not found")
    access_contest(db, s.contest_id, user)
    return submission_public(db, s, user, True)


@router.post("/submissions/{sid}/rejudge", status_code=202)
def rejudge(sid: int, user=Depends(teacher), db: DBSession = Depends(get_db)):
    lock_write(db)
    s = db.get(Submission, sid)
    if not s:
        raise HTTPException(404, "Submission not found")
    owned(db.get(Contest, s.contest_id), user)
    if s.status in ("QUEUED", "RUNNING"):
        raise HTTPException(409, "Already queued")
    if not judge_status(db)["judge_available"]:
        raise HTTPException(503, "Sandbox unavailable")
    from ..services.rejudging import reset_submission, capacity

    if capacity(db) <= 0:
        raise HTTPException(429, "Judge queue is full")
    reset_submission(db, s, user)
    db.commit()
    return submission_public(db, s, user)


@router.patch("/submissions/{sid}/feedback")
def feedback(
    sid: int, req: S.FeedbackIn, user=Depends(teacher), db: DBSession = Depends(get_db)
):
    lock_write(db)
    s = db.get(Submission, sid)
    if not s:
        raise HTTPException(404, "Submission not found")
    owned(db.get(Contest, s.contest_id), user)
    s.feedback = req.feedback
    audit(db, user, "submission.feedback", sid)
    db.commit()
    return submission_public(db, s, user, True)
