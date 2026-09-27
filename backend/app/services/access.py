import time
from fastapi import HTTPException
from sqlalchemy import select
from ..models import (
    Contest,
    ContestGroup,
    ContestParticipant,
    ContestProblem,
    GroupMember,
    Problem,
    TeamMember,
)


def contest_status(c, now=None):
    now = time.time() if now is None else now
    if c.status in ("DRAFT", "PAUSED", "FINISHED", "ARCHIVED"):
        return c.status
    if now >= c.end_time:
        return "FINISHED"
    return "RUNNING" if now >= c.start_time else "SCHEDULED"


def manager(c, u):
    return u.role == "ADMIN" or (u.role == "TEACHER" and c.author_id == u.id)


def participant_ids(db, c):
    direct = set(
        db.scalars(
            select(ContestParticipant.user_id).where(
                ContestParticipant.contest_id == c.id
            )
        )
    )
    groups = select(ContestGroup.group_id).where(ContestGroup.contest_id == c.id)
    direct.update(
        db.scalars(select(GroupMember.user_id).where(GroupMember.group_id.in_(groups)))
    )
    direct.update(
        db.scalars(select(TeamMember.user_id).where(TeamMember.contest_id == c.id))
    )
    return direct


def access_contest(db, cid, u, active=False):
    c = db.get(Contest, cid)
    if not c or (
        not manager(c, u)
        and (
            u.role != "STUDENT"
            or u.id not in participant_ids(db, c)
            or c.status in ("DRAFT", "ARCHIVED")
        )
    ):
        raise HTTPException(404, "Contest not found")
    if active and contest_status(c) != "RUNNING":
        raise HTTPException(403, "Contest is not running")
    return c


def problem_pairs(db, c):
    return db.execute(
        select(Problem, ContestProblem)
        .join(ContestProblem, ContestProblem.problem_id == Problem.id)
        .where(ContestProblem.contest_id == c.id)
        .order_by(ContestProblem.ordinal)
    ).all()


def team_id_for(db, cid, uid):
    return db.scalar(
        select(TeamMember.team_id).where(
            TeamMember.contest_id == cid, TeamMember.user_id == uid
        )
    )


def conversation_user_ids(db, c, user):
    team = team_id_for(db, c.id, user.id) if c.mode == "TEAM" else None
    return (
        list(
            db.scalars(
                select(TeamMember.user_id).where(
                    TeamMember.contest_id == c.id, TeamMember.team_id == team
                )
            )
        )
        if team
        else [user.id]
    )
