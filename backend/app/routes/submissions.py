from ..services.submission_queue import enqueue_submission
import time
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, delete, or_
from sqlalchemy.orm import Session as DBSession
from ..db import get_db, lock_write
from ..models import (
    Contest,
    Problem,
    Submission,
    SubmissionTestResult,
    TestCase,
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
            "kind", "language", "team_id", "is_practice", "score", "feedback",
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
    limit: int = Query(100, ge=1, le=500),
    user=Depends(current_user),
    db: DBSession = Depends(get_db),
):
    q = select(Submission)
    if contest_id:
        c = access_contest(db, contest_id, user)
        q = q.where(Submission.contest_id == c.id)
        if not manager(c, user):
            q = q.where(or_(Submission.user_id == user.id, Submission.team_id == (team_id_for(db, c.id, user.id) or -1)))
    elif user.role == "STUDENT":
        q = q.where(Submission.user_id == user.id)
    elif user.role == "TEACHER":
        q = q.where(
            Submission.contest_id.in_(
                select(Contest.id).where(Contest.author_id == user.id)
            )
        )
    if problem_id:
        q = q.where(Submission.problem_id == problem_id)
    if status:
        q = q.where(Submission.status == status)
    return [
        submission_public(db, s, user)
        for s in db.scalars(
            q.order_by(Submission.created_at.desc(), Submission.id.desc()).limit(limit)
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
    s.history = [
        *(s.history or []),
        {
            "status": s.status, "score": s.score,
            "finished_at": s.finished_at,
            "time_ms": s.time_ms,
            "version": s.problem_snapshot.get("version"),
            "rejudged_at": time.time(),
        },
    ]
    p = db.get(Problem, s.problem_id)
    tests = db.scalars(
        select(TestCase).where(TestCase.problem_id == p.id).order_by(TestCase.ordinal)
    ).all()
    s.problem_snapshot = {
        "version": p.version,
        "scoring": s.problem_snapshot.get("scoring", "ICPC"),
        "time_limit": p.time_limit,
        "mem_limit": p.mem_limit,
        "tests": [
            {
                "input_data": t.input_data,
                "expected": t.expected,
                "is_sample": t.is_sample, "weight": t.weight,
            }
            for t in tests
            if s.kind == "SUBMIT" or t.is_sample
        ],
    }
    s.status = "QUEUED"
    s.started_at = None
    s.finished_at = None
    s.lease_token = None
    s.attempt_count = 0
    s.error = ""
    s.time_ms = 0
    s.score = 0
    db.execute(
        delete(SubmissionTestResult).where(SubmissionTestResult.submission_id == sid)
    )
    audit(db, user, "submission.rejudge", sid)
    db.commit()
    return submission_public(db, s, user)


@router.patch("/submissions/{sid}/feedback")
def feedback(sid: int, req: S.FeedbackIn, user=Depends(teacher), db: DBSession = Depends(get_db)):
    lock_write(db)
    s = db.get(Submission, sid)
    if not s:
        raise HTTPException(404, "Submission not found")
    owned(db.get(Contest, s.contest_id), user)
    s.feedback = req.feedback
    audit(db, user, "submission.feedback", sid)
    db.commit()
    return submission_public(db, s, user, True)
