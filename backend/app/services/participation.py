"""Private participant progress and explicit submission closure."""

from sqlalchemy import select
from sqlalchemy.orm import load_only
from ..models import ParticipationCompletion, Submission, ContestProblem
from .access import team_id_for
from .scoreboard import historical_result


def identity_for(db, c, user):
    team = team_id_for(db, c.id, user.id) if c.mode == "TEAM" else None
    return f"t:{team}" if team else f"u:{user.id}"


def completed(db, c, user):
    return db.get(ParticipationCompletion, (c.id, identity_for(db, c, user)))


def progress(db, c, user):
    identity = identity_for(db, c, user)
    q = select(Submission).where(
        Submission.contest_id == c.id, Submission.is_practice.is_(False)
    )
    q = (
        q.where(Submission.team_id == int(identity[2:]))
        if identity.startswith("t:")
        else q.where(Submission.user_id == user.id)
    )
    rows = db.scalars(
        q.options(
            load_only(
                Submission.id,
                Submission.problem_id,
                Submission.kind,
                Submission.status,
                Submission.finished_at,
                Submission.history,
                Submission.score,
            )
        ).order_by(Submission.id)
    ).all()
    problems = list(
        db.scalars(
            select(ContestProblem.problem_id)
            .where(ContestProblem.contest_id == c.id)
            .order_by(ContestProblem.ordinal)
        )
    )
    solved = set()
    latest = {}
    for s in rows:
        if s.kind != "SUBMIT":
            continue
        latest[s.problem_id] = s.status
        if historical_result(s, float("inf"))[0] == "ACCEPTED":
            solved.add(s.problem_id)
    completion = completed(db, c, user)
    return {
        "solved": len(solved.intersection(problems)),
        "total": len(problems),
        "solved_ids": [p for p in problems if p in solved],
        "last_verdicts": latest,
        "pending": sum(s.status in ("QUEUED", "RUNNING") for s in rows),
        "completed_at": completion.completed_at if completion else None,
        "team": c.mode == "TEAM",
    }
