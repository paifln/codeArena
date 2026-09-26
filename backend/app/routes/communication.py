import csv
import io
import time
from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import select, func, or_
from sqlalchemy.orm import Session as DBSession
from ..db import get_db
from ..models import (
    Announcement,
    AuditLog,
    Clarification,
    Contest,
    ContestProblem,
    Group,
    Submission,
    User,
)
from .. import schemas as S
from ..security import current_user, teacher, admin, owned, user_public, throttle
from ..services import (
    access_contest,
    audit,
    iso,
    manager,
    participant_ids,
    scoreboard,
    contest_status,
)

router = APIRouter()


@router.get("/dashboard")
def dashboard(user=Depends(current_user), db: DBSession = Depends(get_db)):
    visible = [
        c
        for c in db.scalars(select(Contest))
        if manager(c, user)
        or (
            user.role == "STUDENT"
            and c.status not in ("DRAFT", "ARCHIVED")
            and user.id in participant_ids(db, c)
        )
    ]
    ids = [c.id for c in visible]
    query = select(Submission).where(
        Submission.kind == "SUBMIT", Submission.contest_id.in_(ids)
    )
    if user.role == "STUDENT":
        query = query.where(Submission.user_id == user.id)
    rows = db.scalars(query).all()
    accepted = sum(s.status == "ACCEPTED" for s in rows)
    groups = select(func.count()).select_from(Group)
    students = select(func.count()).select_from(User).where(User.role == "STUDENT")
    if user.role != "ADMIN":
        groups = groups.where(Group.author_id == user.id)
        students = students.where(User.creator_id == user.id)
    return {
        "contests": len(ids),
        "active_contests": sum(contest_status(c) == "RUNNING" for c in visible),
        "groups": db.scalar(groups) if user.role != "STUDENT" else 0,
        "students": db.scalar(students) if user.role != "STUDENT" else 0,
        "submissions": len(rows),
        "accepted": accepted,
        "solved": len(
            {(s.contest_id, s.problem_id) for s in rows if s.status == "ACCEPTED"}
        ),
        "acceptance_rate": round(accepted / max(len(rows), 1) * 100, 1),
    }


@router.get("/contests/{cid}/scoreboard")
def standings(cid: int, user=Depends(current_user), db: DBSession = Depends(get_db)):
    return scoreboard(db, access_contest(db, cid, user), user)


@router.get("/contests/{cid}/scoreboard.csv")
def standings_csv(cid: int, user=Depends(teacher), db: DBSession = Depends(get_db)):
    c = owned(db.get(Contest, cid), user)
    data = scoreboard(db, c, user)
    out = io.StringIO()
    writer = csv.writer(out)
    writer.writerow(["Rank", "Name", "Username", "Solved", "Penalty"])

    def safe_cell(text):
        return "'" + text if text and text[0] in "=+-@\t\r" else text

    for r in data["rows"]:
        writer.writerow(
            [
                r["rank"],
                safe_cell(r["name"]),
                safe_cell(r["username"]),
                r["solved"],
                r["penalty"],
            ]
        )
    return Response(
        "\ufeff" + out.getvalue(),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="contest-{cid}.csv"'},
    )


@router.get("/contests/{cid}/monitor")
def monitor(cid: int, user=Depends(teacher), db: DBSession = Depends(get_db)):
    c = owned(db.get(Contest, cid), user)
    ids = participant_ids(db, c)
    entries = []
    for u in db.scalars(select(User).where(User.id.in_(ids))):
        latest = db.scalar(
            select(func.max(Submission.created_at)).where(
                Submission.contest_id == cid, Submission.user_id == u.id
            )
        )
        entries.append(
            {
                **user_public(u),
                "online": time.time() - (u.last_seen or 0) < 45,
                "last_activity": iso(latest),
            }
        )
    return {"participants": entries, **scoreboard(db, c, user)}


@router.post("/heartbeat")
def heartbeat(user=Depends(current_user), db: DBSession = Depends(get_db)):
    db.get(User, user.id).last_seen = time.time()
    db.commit()
    return {"server_time": iso(time.time())}


@router.get("/contests/{cid}/clarifications")
def questions(cid: int, user=Depends(current_user), db: DBSession = Depends(get_db)):
    c = access_contest(db, cid, user)
    q = select(Clarification).where(Clarification.contest_id == cid)
    if not manager(c, user):
        q = q.where(
            or_(Clarification.user_id == user.id, Clarification.is_public == True)
        )
    return [
        {
            "id": a.id,
            "question": a.question,
            "answer": a.answer,
            "is_public": a.is_public,
            "problem_id": a.problem_id,
            "user_id": a.user_id,
            "created_at": iso(a.created_at),
        }
        for a in db.scalars(q.order_by(Clarification.created_at.desc()))
    ]


@router.post("/contests/{cid}/clarifications", status_code=201)
def ask(
    cid: int,
    req: S.Question,
    user=Depends(current_user),
    db: DBSession = Depends(get_db),
):
    access_contest(db, cid, user)
    if req.problem_id and not db.get(ContestProblem, (cid, req.problem_id)):
        raise HTTPException(404, "Problem not found")
    throttle(db, f"question:{user.id}", 10, 60)
    q = Clarification(contest_id=cid, user_id=user.id, **req.model_dump())
    db.add(q)
    db.commit()
    return {"id": q.id, "question": q.question, "answer": "", "is_public": False}


@router.patch("/clarifications/{qid}")
def answer(
    qid: int, req: S.Answer, user=Depends(teacher), db: DBSession = Depends(get_db)
):
    q = db.get(Clarification, qid)
    if not q:
        raise HTTPException(404, "Not found")
    owned(db.get(Contest, q.contest_id), user)
    q.answer = req.answer
    q.is_public = req.is_public
    audit(db, user, "clarification.answer", qid, {"is_public": req.is_public})
    db.commit()
    return {"id": q.id, "answer": q.answer, "is_public": q.is_public}


@router.get("/contests/{cid}/announcements")
def announcements(
    cid: int, user=Depends(current_user), db: DBSession = Depends(get_db)
):
    access_contest(db, cid, user)
    return [
        {
            "id": a.id,
            "message": a.message,
            "level": a.level,
            "created_at": iso(a.created_at),
        }
        for a in db.scalars(
            select(Announcement)
            .where(Announcement.contest_id == cid)
            .order_by(Announcement.created_at.desc())
        )
    ]


@router.post("/contests/{cid}/announcements", status_code=201)
def announce(
    cid: int,
    req: S.AnnouncementIn,
    user=Depends(teacher),
    db: DBSession = Depends(get_db),
):
    owned(db.get(Contest, cid), user)
    a = Announcement(contest_id=cid, author_id=user.id, **req.model_dump())
    db.add(a)
    db.flush()
    audit(db, user, "announcement.create", a.id)
    db.commit()
    return {"id": a.id, "message": a.message, "level": a.level}


@router.get("/audit")
def audit_logs(user=Depends(admin), db: DBSession = Depends(get_db)):
    return [
        {
            "id": a.id,
            "user_id": a.user_id,
            "action": a.action,
            "entity_id": a.entity_id,
            "detail": a.detail,
            "created_at": iso(a.created_at),
        }
        for a in db.scalars(select(AuditLog).order_by(AuditLog.id.desc()).limit(300))
    ]
