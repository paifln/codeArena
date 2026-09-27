import time
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session as DBSession
from ..db import get_db, lock_write
from ..models import (
    Contest,
    ContestGroup,
    ContestParticipant,
    ContestProblem,
    Group,
    Problem,
    User,
    Team,
    TeamMember,
)
from .. import schemas as S
from ..security import current_user, teacher, owned
from ..services import (
    access_contest,
    audit,
    contest_public,
    contest_status,
    manager,
    participant_ids,
)

router = APIRouter()


@router.get("/contests")
def contests(user=Depends(current_user), db: DBSession = Depends(get_db)):
    all_c = db.scalars(select(Contest).order_by(Contest.start_time.desc())).all()
    return [
        contest_public(db, c, user)
        for c in all_c
        if manager(c, user)
        or (
            user.role == "STUDENT"
            and c.status not in ("DRAFT", "ARCHIVED")
            and user.id in participant_ids(db, c)
        )
    ]


@router.post("/contests", status_code=201)
def create_contest(
    req: S.ContestIn, user=Depends(teacher), db: DBSession = Depends(get_db)
):
    lock_write(db)
    for pid in req.problem_ids:
        owned(db.get(Problem, pid), user)
    for gid in req.group_ids:
        owned(db.get(Group, gid), user)
    for uid in [
        *req.participant_ids,
        *(uid for team in req.teams for uid in team.user_ids),
    ]:
        u = db.get(User, uid)
        if (
            not u
            or not u.active
            or u.role != "STUDENT"
            or (user.role != "ADMIN" and u.creator_id != user.id)
        ):
            raise HTTPException(404, "Student not found")
    c = Contest(
        **req.model_dump(
            exclude={
                "teams",
                "freeze_minutes",
                "problem_ids",
                "group_ids",
                "participant_ids",
                "start_time",
                "end_time",
            }
        ),
        start_time=req.start_time.timestamp(),
        end_time=req.end_time.timestamp(),
        author_id=user.id,
        status="SCHEDULED",
        freeze_at=req.end_time.timestamp() - req.freeze_minutes * 60
        if req.freeze_minutes
        else None,
    )
    db.add(c)
    db.flush()
    for i, pid in enumerate(req.problem_ids):
        db.add(ContestProblem(contest_id=c.id, problem_id=pid, ordinal=i))
    for gid in set(req.group_ids):
        db.add(ContestGroup(contest_id=c.id, group_id=gid))
    for uid in set(req.participant_ids):
        db.add(ContestParticipant(contest_id=c.id, user_id=uid))
    for item in req.teams:
        team = Team(contest_id=c.id, name=item.name, organization=item.organization)
        db.add(team)
        db.flush()
        for uid in item.user_ids:
            db.add(TeamMember(contest_id=c.id, team_id=team.id, user_id=uid))
    audit(db, user, "contest.create", c.id, contest_id=c.id)
    db.commit()
    return contest_public(db, c, user)


@router.get("/contests/{cid}")
def contest_detail(
    cid: int, user=Depends(current_user), db: DBSession = Depends(get_db)
):
    c = access_contest(db, cid, user)
    return contest_public(db, c, user)


@router.patch("/contests/{cid}/practice")
def configure_practice(
    cid: int,
    req: S.PracticeSettings,
    user=Depends(teacher),
    db: DBSession = Depends(get_db),
):
    lock_write(db)
    c = owned(db.get(Contest, cid), user)
    c.practice_enabled = req.practice_enabled
    audit(db, user, "contest.practice", cid, {"enabled": req.practice_enabled})
    db.commit()
    return contest_public(db, c, user)


def transition(db, cid, user, action, minutes=0):
    lock_write(db)
    c = owned(db.get(Contest, cid), user)
    now = time.time()
    state = contest_status(c, now)
    old = {
        "status": state,
        "start_time": c.start_time,
        "end_time": c.end_time,
        "freeze_at": c.freeze_at,
    }
    if action == "start" and state in ("SCHEDULED", "DRAFT"):
        duration = c.end_time - c.start_time
        if c.freeze_at is not None:
            c.freeze_at += now - c.start_time
        c.start_time = now
        c.end_time = now + duration
        c.status = "RUNNING"
    elif action == "pause" and state == "RUNNING":
        c.status = "PAUSED"
        c.paused_at = now
    elif action == "resume" and state == "PAUSED":
        elapsed = now - c.paused_at
        if c.freeze_at is not None and c.freeze_at > c.paused_at:
            c.freeze_at += elapsed
        c.end_time += elapsed
        c.paused_seconds += elapsed
        c.paused_at = None
        c.status = "RUNNING"
    elif action == "finish" and state in ("RUNNING", "PAUSED", "SCHEDULED"):
        c.status = "FINISHED"
    elif action == "extend" and state in ("SCHEDULED", "RUNNING", "PAUSED"):
        c.end_time += minutes * 60
        if c.freeze_at is not None and c.freeze_at > (c.paused_at or now):
            c.freeze_at += minutes * 60
    elif action == "freeze" and state in ("RUNNING", "PAUSED"):
        c.freeze_at = now
    elif action == "unfreeze" and c.freeze_at is not None:
        c.freeze_at = None
        c.revealed_ids = []
    else:
        raise HTTPException(409, "Invalid contest transition")
    audit(
        db,
        user,
        "contest." + action,
        c.id,
        {
            "old": old,
            "new": {
                "status": c.status,
                "start_time": c.start_time,
                "end_time": c.end_time,
                "freeze_at": c.freeze_at,
            },
        },
        contest_id=c.id,
    )
    db.commit()
    return contest_public(db, c, user)


@router.post("/contests/{cid}/extend")
def extend(
    cid: int, req: S.Extend, user=Depends(teacher), db: DBSession = Depends(get_db)
):
    return transition(db, cid, user, "extend", req.minutes)


@router.post("/contests/{cid}/start")
@router.post("/contests/{cid}/pause")
@router.post("/contests/{cid}/resume")
@router.post("/contests/{cid}/finish")
@router.post("/contests/{cid}/freeze")
@router.post("/contests/{cid}/unfreeze")
def control(
    cid: int, request: Request, user=Depends(teacher), db: DBSession = Depends(get_db)
):
    action = request.url.path.rsplit("/", 1)[-1]
    return transition(db, cid, user, action)
