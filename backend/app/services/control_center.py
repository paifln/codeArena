import time
from collections import Counter
from sqlalchemy import select
from sqlalchemy.orm import defer
from ..models import (
    Submission,
    User,
    Team,
    TeamMember,
    ContestPresence,
    Clarification,
    AuditLog,
    SystemSetting,
    RejudgeBatch,
    ParticipationCompletion,
)
from .access import participant_ids, problem_pairs
from .judge_health import judge_status
from .scoreboard import scoreboard


def identities(db, c):
    if c.mode == "TEAM":
        return [
            {
                "identity": f"t:{t.id}",
                "name": t.name,
                "organization": t.organization,
                "members": [
                    {"id": u.id, "name": u.name, "username": u.username}
                    for u in db.scalars(
                        select(User)
                        .join(TeamMember, TeamMember.user_id == User.id)
                        .where(TeamMember.team_id == t.id)
                    )
                ],
            }
            for t in db.scalars(select(Team).where(Team.contest_id == c.id))
        ]
    return [
        {
            "identity": f"u:{u.id}",
            "name": u.name,
            "organization": "",
            "members": [{"id": u.id, "name": u.name, "username": u.username}],
        }
        for u in db.scalars(select(User).where(User.id.in_(participant_ids(db, c))))
    ]


def control_data(db, c, user):
    now = time.time()
    rows = db.scalars(
        select(Submission)
        .options(
            defer(Submission.source),
            defer(Submission.problem_snapshot),
            defer(Submission.history),
            defer(Submission.custom_input),
            defer(Submission.error),
        )
        .where(Submission.contest_id == c.id)
        .order_by(Submission.id.desc())
    ).all()
    official = [s for s in rows if s.kind == "SUBMIT" and not s.is_practice]
    board = scoreboard(db, c, user)
    presence = {
        p.user_id: p.last_seen
        for p in db.scalars(
            select(ContestPresence).where(ContestPresence.contest_id == c.id)
        )
    }
    completions = {
        r.identity: r.completed_at
        for r in db.scalars(
            select(ParticipationCompletion).where(
                ParticipationCompletion.contest_id == c.id
            )
        )
    }
    teams = identities(db, c)
    for team in teams:
        team["completed_at"] = completions.get(team["identity"])
        team["last_seen"] = max(
            (presence.get(m["id"], 0) for m in team["members"]), default=0
        )
        team["online"] = team["last_seen"] >= now - 60
    problems = []
    for p, cp in problem_pairs(db, c):
        submissions = [s for s in official if s.problem_id == p.id]
        cells = [
            x for row in board["rows"] for x in row["cells"] if x["problem_id"] == p.id
        ]
        solved = sum(x["solved"] for x in cells)
        first = next(
            (x.get("first_solve") for x in board["problems"] if x["id"] == p.id), None
        )
        attempts = []
        for team in teams:
            trial = sorted(
                [
                    s
                    for s in submissions
                    if (f"t:{s.team_id}" if c.mode == "TEAM" else f"u:{s.user_id}")
                    == team["identity"]
                ],
                key=lambda s: (s.created_at, s.id),
            )
            accepted = next(
                (i for i, s in enumerate(trial) if s.status == "ACCEPTED"), None
            )
            if accepted is not None:
                attempts.append(accepted + 1)
        problems.append(
            {
                "id": p.id,
                "letter": chr(65 + cp.ordinal),
                "title": p.title,
                "attempts": len(submissions),
                "solved": solved,
                "solve_rate": round(100 * solved / max(len(teams), 1), 1),
                "verdicts": dict(Counter(s.status for s in submissions)),
                "first_solve": first,
                "average_attempts": round(sum(attempts) / len(attempts), 2)
                if attempts
                else None,
            }
        )
    events = [
        {
            "id": e.id,
            "type": e.action,
            "entity_id": e.entity_id,
            "user_id": e.user_id,
            "time": e.created_at,
            "detail": e.detail,
        }
        for e in db.scalars(
            select(AuditLog)
            .where(AuditLog.contest_id == c.id)
            .order_by(AuditLog.id.desc())
            .limit(100)
        )
    ]
    durations = [
        s.finished_at - s.started_at for s in rows if s.finished_at and s.started_at
    ]
    heartbeat = db.get(SystemSetting, "judge_heartbeat")
    health = judge_status(db)
    running = [s for s in rows if s.status == "RUNNING"]
    count = heartbeat.value.get("slots", 2) if heartbeat else 0
    occupied = len(
        db.scalars(select(Submission.id).where(Submission.status == "RUNNING")).all()
    )
    slow = [s.id for s in running if s.started_at and now - s.started_at > 120]
    return {
        "teams": teams,
        "problems": problems,
        "events": events,
        "total_submissions": len(official),
        "queued": sum(s.status == "QUEUED" for s in rows),
        "judging": len(running),
        "open_questions": len(
            db.scalars(
                select(Clarification).where(
                    Clarification.contest_id == c.id, Clarification.status == "OPEN"
                )
            ).all()
        ),
        "judge": {
            **health,
            "state": "Offline"
            if not health["judge_available"]
            else "Degraded"
            if slow
            else "Healthy",
            "slots": count,
            "busy_slots": occupied,
            "average_seconds": round(sum(durations) / len(durations), 2)
            if durations
            else None,
            "total_judged": len(durations),
            "running": [
                {"id": s.id, "seconds": round(now - s.started_at)} for s in running
            ],
            "languages": c.languages,
        },
        "alerts": {
            "disconnected": [
                t["name"] for t in teams if t["last_seen"] and not t["online"]
            ],
            "slow_submissions": slow,
        },
        "batches": [
            {
                "id": b.id,
                "total": b.total,
                "remaining": len(b.remaining_ids),
                "queued_at": b.finished_at,
            }
            for b in db.scalars(
                select(RejudgeBatch)
                .where(RejudgeBatch.contest_id == c.id)
                .order_by(RejudgeBatch.id.desc())
                .limit(10)
            )
        ],
    }
