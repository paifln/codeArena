"""Persist contest events in the existing audit ledger, in the owning transaction."""

import time
from sqlalchemy import select
from ..models import (
    AuditLog,
    Contest,
    ContestPresence,
    PuzzleReward,
    Submission,
    User,
    Team,
    ContestProblem,
)
from .access import contest_status, participant_ids
from .common import audit
from .scoreboard import freeze_cutoff, historical_result


def emit(db, cid, action, entity_id=None, detail=None, user=None):
    audit(db, user, action, entity_id, detail, contest_id=cid)


def reward_identity(c, s):
    return (
        f"t:{s.team_id}"
        if c.mode == "TEAM" and s.team_id
        else f"u:{s.user_id}"
        if c.mode != "TEAM"
        else None
    )


def reconcile_rewards(db, c):
    """One physical piece per team/problem. Rejudge never duplicates delivery."""
    members = participant_ids(db, c)
    accepted = db.scalars(
        select(Submission)
        .where(
            Submission.contest_id == c.id,
            Submission.kind == "SUBMIT",
            Submission.is_practice.is_(False),
        )
        .order_by(Submission.created_at, Submission.id)
    ).all()
    winners = {}
    for s in accepted:
        if historical_result(s, float("inf"))[0] != "ACCEPTED":
            continue
        identity = reward_identity(c, s)
        if identity and s.user_id in members:
            winners.setdefault((identity, s.problem_id), s)
    existing = {
        (r.identity, r.problem_id): r
        for r in db.scalars(select(PuzzleReward).where(PuzzleReward.contest_id == c.id))
    }
    letters = {
        p.problem_id: chr(65 + p.ordinal)
        for p in db.scalars(
            select(ContestProblem).where(ContestProblem.contest_id == c.id)
        )
    }
    for key, s in winners.items():
        reward = existing.get(key)
        if reward is None:
            reward = PuzzleReward(
                contest_id=c.id,
                identity=key[0],
                problem_id=s.problem_id,
                submission_id=s.id,
                solved_at=s.created_at,
                revoked=False,
            )
            db.add(reward)
            entity = db.get(Team, s.team_id) if s.team_id else db.get(User, s.user_id)
            detail = {
                "identity": key[0],
                "problem_id": s.problem_id,
                "name": entity.name if entity else "",
                "letter": letters.get(s.problem_id, ""),
            }
            emit(db, c.id, "problem.solved", s.id, detail)
            if not any(k[1] == s.problem_id for k in existing):
                emit(db, c.id, "problem.first_solve", s.id, detail)
            existing[key] = reward
        reward.revoked = False
        reward.submission_id = s.id
        reward.solved_at = s.created_at
    for key, reward in existing.items():
        if key not in winners:
            reward.revoked = True


def judged(db, s):
    entity = db.get(Team, s.team_id) if s.team_id else db.get(User, s.user_id)
    emit(
        db,
        s.contest_id,
        "submission.judged",
        s.id,
        {
            "name": entity.name if entity else "",
            "status": s.status,
            "score": s.score,
            "problem_id": s.problem_id,
            "user_id": s.user_id,
            "team_id": s.team_id,
            "elapsed": s.contest_elapsed,
            "kind": s.kind,
            "practice": s.is_practice,
        },
    )
    reconcile_rewards(db, db.get(Contest, s.contest_id))


def touch_presence(db, c, user):
    now = time.time()
    row = db.get(ContestPresence, (c.id, user.id))
    if row is None:
        row = ContestPresence(
            contest_id=c.id, user_id=user.id, last_seen=now, connected=True
        )
        db.add(row)
        emit(db, c.id, "team.connected", user.id, {"name": user.name}, user=user)
    elif not row.connected or row.last_seen < now - 60:
        row.connected = True
        emit(db, c.id, "team.connected", user.id, {"name": user.name}, user=user)
    row.last_seen = now


def lifecycle(db):
    now = time.time()
    for row in db.scalars(
        select(ContestPresence).where(
            ContestPresence.connected.is_(True), ContestPresence.last_seen < now - 60
        )
    ):
        row.connected = False
        emit(db, row.contest_id, "team.disconnected", row.user_id)
    for c in db.scalars(
        select(Contest).where(
            Contest.status.in_(["SCHEDULED", "RUNNING", "PAUSED", "FINISHED"])
        )
    ):
        if not db.scalar(
            select(AuditLog.id)
            .where(AuditLog.contest_id == c.id, AuditLog.action == "puzzle.initialized")
            .limit(1)
        ):
            reconcile_rewards(db, c)
            emit(db, c.id, "puzzle.initialized", c.id)
        state = contest_status(c)
        actions = []
        if state in ("RUNNING", "FINISHED"):
            actions.append("contest.start")
        if state == "FINISHED":
            actions.append("contest.finish")
        if freeze_cutoff(c) is not None:
            actions.append("contest.freeze")
        for action in actions:
            if not db.scalar(
                select(AuditLog.id)
                .where(AuditLog.contest_id == c.id, AuditLog.action == action)
                .limit(1)
            ):
                emit(db, c.id, action, c.id, {"automatic": True})
