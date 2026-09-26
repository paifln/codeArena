import time
from fastapi import HTTPException
from sqlalchemy import select
from ..models import Submission, User
from .access import contest_status, manager, participant_ids, problem_pairs
from .common import iso

PENALIZED = {
    "WRONG_ANSWER",
    "TIME_LIMIT_EXCEEDED",
    "MEMORY_LIMIT_EXCEEDED",
    "RUNTIME_ERROR",
    "COMPILATION_ERROR",
    "OUTPUT_LIMIT_EXCEEDED",
}


def scoreboard(db, c, u):
    privileged = manager(c, u)
    if not privileged and (
        not c.scoreboard_enabled or contest_status(c) in ("DRAFT", "SCHEDULED")
    ):
        raise HTTPException(403, "Scoreboard is unavailable")
    pairs = problem_pairs(db, c)
    problem_list = [
        {"id": p.id, "title": p.title, "letter": chr(65 + cp.ordinal)}
        for p, cp in pairs
    ]
    members = participant_ids(db, c)
    query = (
        select(Submission)
        .where(Submission.contest_id == c.id, Submission.kind == "SUBMIT")
        .order_by(Submission.created_at, Submission.id)
    )
    subs = db.scalars(query).all()
    frozen = c.freeze_at is not None and not privileged
    cells = {}
    for s in subs:
        if frozen and s.created_at >= c.freeze_at:
            continue
        # Rejudge history preserves the verdict visible at freeze time.
        verdict = s.status
        if frozen and (not s.finished_at or s.finished_at >= c.freeze_at):
            prior = [
                h
                for h in (s.history or [])
                if h.get("finished_at") and h["finished_at"] < c.freeze_at
            ]
            if not prior:
                continue
            verdict = prior[-1]["status"]
        key = (s.user_id, s.problem_id)
        cell = cells.setdefault(
            key, {"attempts": 0, "solved": False, "minutes": None, "penalty": 0}
        )
        if cell["solved"]:
            continue
        if verdict == "ACCEPTED":
            cell["solved"] = True
            cell["minutes"] = int(s.contest_elapsed // 60)
            cell["penalty"] = cell["minutes"] + 20 * cell["attempts"]
        elif verdict in PENALIZED:
            cell["attempts"] += 1
    rows = []
    users = (
        db.scalars(select(User).where(User.id.in_(members)).order_by(User.id)).all()
        if members
        else []
    )
    for user in users:
        row_cells = [
            dict(
                cells.get(
                    (user.id, p["id"]),
                    {"attempts": 0, "solved": False, "minutes": None, "penalty": 0},
                ),
                problem_id=p["id"],
                letter=p["letter"],
            )
            for p in problem_list
        ]
        rows.append(
            {
                "user_id": user.id,
                "name": user.name,
                "username": user.username,
                "solved": sum(t["solved"] for t in row_cells),
                "penalty": sum(t["penalty"] for t in row_cells),
                "cells": row_cells,
            }
        )
    rows.sort(key=lambda r: (-r["solved"], r["penalty"], r["user_id"]))
    for rank, row in enumerate(rows, 1):
        row["rank"] = rank
    return {
        "rows": rows,
        "problems": problem_list,
        "frozen": frozen,
        "server_time": iso(time.time()),
    }
