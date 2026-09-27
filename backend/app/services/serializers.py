import time
from sqlalchemy import select
from ..models import TestCase, Team, TeamMember
from .access import contest_status, manager, participant_ids, problem_pairs
from .common import iso
from .execution import execution_policy


def contest_public(db, c, u):
    state = contest_status(c)
    reveal = manager(c, u) or state in ("RUNNING", "PAUSED", "FINISHED")
    pairs = problem_pairs(db, c)
    return {
        "id": c.id,
        "mode": c.mode, "scoring": c.scoring, "practice_enabled": c.practice_enabled,
        "practice_execution": execution_policy(db, c, practice=True),
        "teams": [{"id": team.id, "name": team.name, "user_ids": list(db.scalars(select(TeamMember.user_id).where(TeamMember.team_id == team.id)))} for team in db.scalars(select(Team).where(Team.contest_id == c.id))],
        "title": c.title,
        "description": c.description,
        "rules": c.rules,
        "status": state,
        "execution": execution_policy(db, c),
        "can_manage": manager(c, u),
        "start_time": iso(c.start_time),
        "end_time": iso(c.end_time),
        "server_time": iso(time.time()),
        "paused_at": iso(c.paused_at),
        "scoreboard_enabled": c.scoreboard_enabled,
        "frozen": c.freeze_at is not None,
        "author_id": c.author_id,
        "participant_count": len(participant_ids(db, c)),
        "problem_count": len(pairs),
        "problems": [
            {
                "id": p.id,
                "title": p.title,
                "letter": chr(65 + cp.ordinal),
                "difficulty": p.difficulty
                if c.show_problem_difficulty or manager(c, u)
                else None,
            }
            for p, cp in pairs
        ]
        if reveal
        else [],
    }


def problem_public(db, p, teacher=False, language="ru"):
    data = {
        k: getattr(p, k)
        for k in (
            "id",
            "title",
            "slug",
            "description",
            "input_fmt",
            "output_fmt",
            "constraints",
            "difficulty",
            "time_limit",
            "mem_limit",
            "tags",
            "version",
            "author_id",
        )
    }
    translation = (p.translations or {}).get(language, {})
    for key in ("title", "description", "input_fmt", "output_fmt", "constraints"):
        if isinstance(translation.get(key), str):
            data[key] = translation[key]
    tests = db.scalars(
        select(TestCase).where(TestCase.problem_id == p.id).order_by(TestCase.ordinal)
    ).all()
    data["tests"] = [
        {"input_data": t.input_data, "expected": t.expected, "is_sample": t.is_sample, **({"weight": t.weight} if teacher else {})}
        for t in tests
        if teacher or t.is_sample
    ]
    data["samples"] = [t for t in data["tests"] if t["is_sample"]]
    if teacher:
        data["editorial"] = p.editorial
        data["translations"] = p.translations
        data["test_count"] = len(tests)
    return data
