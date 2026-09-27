"""Standings policy. Runs and post-contest practice never affect official results."""

import time
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import load_only
from ..models import Submission, User, Team
from .access import contest_status, manager, participant_ids, problem_pairs
from .common import iso

PENALIZED = {
    "WRONG_ANSWER",
    "TIME_LIMIT_EXCEEDED",
    "MEMORY_LIMIT_EXCEEDED",
    "RUNTIME_ERROR",
    "OUTPUT_LIMIT_EXCEEDED",
}


def empty_cell():
    return {
        "attempts": 0,
        "solved": False,
        "minutes": None,
        "penalty": 0,
        "time_minutes": 0,
        "penalty_minutes": 0,
        "score": 0,
        "pending": 0,
        "accepted_at": 0,
    }


def freeze_cutoff(c, now=None):
    now = time.time() if now is None else now
    clock = min(now, c.paused_at) if c.status == "PAUSED" and c.paused_at else now
    return c.freeze_at if c.freeze_at is not None and c.freeze_at <= clock else None


def historical_result(s, at):
    """Immutable prior judgements keep replay/freeze stable during rejudge."""
    versions = [
        h for h in (s.history or []) if h.get("finished_at") and h["finished_at"] <= at
    ]
    if s.finished_at and s.finished_at <= at:
        versions.append(
            {"status": s.status, "score": s.score, "finished_at": s.finished_at}
        )
    if versions:
        result = max(versions, key=lambda h: h["finished_at"])
        return result["status"], result.get(
            "score", 100 if result["status"] == "ACCEPTED" else 0
        )
    # Legacy fixtures/results without a finish timestamp remain usable in live views.
    return (s.status, s.score) if at == float("inf") else ("QUEUED", 0)


def scoreboard(db, c, u=None, *, public=False, at=None):
    privileged = u is not None and manager(c, u) and not public
    if not privileged and (
        not c.scoreboard_enabled or contest_status(c) in ("DRAFT", "SCHEDULED")
    ):
        raise HTTPException(403, "Scoreboard is unavailable")
    problems = [
        {"id": p.id, "title": p.title, "letter": chr(65 + cp.ordinal)}
        for p, cp in problem_pairs(db, c)
    ]
    members = participant_ids(db, c)
    subs = db.scalars(
        select(Submission)
        .options(
            load_only(
                Submission.id,
                Submission.user_id,
                Submission.team_id,
                Submission.problem_id,
                Submission.created_at,
                Submission.finished_at,
                Submission.status,
                Submission.score,
                Submission.history,
                Submission.contest_elapsed,
            )
        )
        .where(
            Submission.contest_id == c.id,
            Submission.kind == "SUBMIT",
            Submission.is_practice.is_(False),
        )
        .order_by(Submission.created_at, Submission.id)
    ).all()
    cutoff = freeze_cutoff(c)
    frozen = cutoff is not None and not privileged
    revealed = set(c.revealed_ids or []) if at is None else set()
    view_at = at if at is not None else float("inf")
    partial = c.scoring == "PARTIAL"
    training = c.scoring == "EDUCATIONAL"
    cells = {}
    for s in subs:
        if s.created_at > view_at:
            continue
        identity = s.team_id if c.mode == "TEAM" else s.user_id
        if identity is None:
            continue  # Teacher test submissions do not represent a team.
        cell = cells.setdefault((identity, s.problem_id), empty_cell())
        hidden = frozen and s.id not in revealed
        if hidden and s.created_at >= cutoff:
            if not cell["solved"]:
                cell["pending"] += 1
            continue
        verdict, score = historical_result(
            s, min(view_at, cutoff - 0.000001) if hidden else view_at
        )
        if (
            hidden
            and s.finished_at
            and s.finished_at >= cutoff
            and any(
                h.get("finished_at") and h["finished_at"] < cutoff
                for h in (s.history or [])
            )
        ):
            cell["pending"] += 1
        if verdict in ("QUEUED", "RUNNING"):
            if not cell["solved"]:
                cell["pending"] += 1
            continue
        if cell["solved"]:
            continue
        if partial:
            if verdict != "SYSTEM_ERROR":
                cell["score"] = max(cell["score"], score)
            if verdict == "ACCEPTED":
                cell["solved"] = True
                cell["score"] = 100
                cell.update(
                    accepted_at=s.contest_elapsed,
                    solved_at=s.created_at,
                    submission_id=s.id,
                )
            continue
        if verdict == "ACCEPTED":
            minutes = int(s.contest_elapsed // 60)
            cell.update(
                solved=True,
                minutes=minutes,
                accepted_at=s.contest_elapsed,
                score=100,
                solved_at=s.created_at,
                submission_id=s.id,
                time_minutes=0 if training else minutes,
                penalty_minutes=0
                if training
                else (c.penalty_minutes if c.penalty_minutes is not None else 20)
                * cell["attempts"],
            )
            cell["penalty"] = cell["time_minutes"] + cell["penalty_minutes"]
        elif verdict in PENALIZED:
            cell["attempts"] += 1
    identities = (
        db.scalars(select(Team).where(Team.contest_id == c.id)).all()
        if c.mode == "TEAM"
        else db.scalars(select(User).where(User.id.in_(members))).all()
    )
    rows = []
    for entity in identities:
        row_cells = [
            dict(
                cells.get((entity.id, p["id"]), empty_cell()),
                problem_id=p["id"],
                letter=p["letter"],
            )
            for p in problems
        ]
        rows.append(
            {
                "user_id": entity.id if c.mode != "TEAM" else None,
                "team_id": entity.id if c.mode == "TEAM" else None,
                "name": entity.name,
                "username": getattr(entity, "username", entity.name),
                "organization": getattr(entity, "organization", ""),
                "solved": sum(x["solved"] for x in row_cells),
                "penalty": sum(x["penalty"] for x in row_cells),
                "score": round(sum(x["score"] for x in row_cells), 2),
                "last_accepted": max((x["accepted_at"] for x in row_cells), default=0),
                "cells": row_cells,
            }
        )

    def rank_key(row):
        if partial:
            return (-row["score"],)
        if training:
            return (-row["solved"],)
        return (-row["solved"], row["penalty"], row["last_accepted"])

    rows.sort(key=lambda row: (*rank_key(row), row["name"].casefold(), row["username"]))
    previous, rank = None, 0
    for index, row in enumerate(rows, 1):
        key = rank_key(row)
        if key != previous:
            rank = index
        row["rank"], previous = rank, key
    for problem in problems:
        solved = [
            (row, cell)
            for row in rows
            for cell in row["cells"]
            if cell["problem_id"] == problem["id"] and cell["solved"]
        ]
        if solved:
            first_row, first_cell = min(
                solved,
                key=lambda pair: (
                    pair[1]["accepted_at"],
                    pair[1].get("submission_id", 0),
                ),
            )
            first_cell["first_solve"] = True
            problem["first_solve"] = {
                "name": first_row["name"],
                "elapsed": first_cell["accepted_at"],
            }
    return {
        "rows": rows,
        "problems": problems,
        "frozen": frozen,
        "mode": c.mode,
        "scoring": c.scoring,
        "title": c.title,
        "status": contest_status(c),
        "start_time": iso(c.start_time),
        "end_time": iso(c.end_time),
        "logo_data": c.logo_data,
        "server_time": iso(time.time()),
    }
