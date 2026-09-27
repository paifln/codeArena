"""The same rejudge transaction serves individual requests and durable batches."""

import os
import time
from sqlalchemy import select, delete, func
from fastapi import HTTPException
from ..models import (
    Contest,
    Submission,
    SubmissionTestResult,
    TestCase,
    Problem,
    RejudgeBatch,
    User,
)
from .contest_events import emit


def reset_submission(db, s, actor):
    if s.status in ("QUEUED", "RUNNING"):
        return False
    s.history = [
        *(s.history or []),
        {
            "status": s.status,
            "score": s.score,
            "finished_at": s.finished_at,
            "time_ms": s.time_ms,
            "memory_kb": s.memory_kb,
            "version": s.problem_snapshot.get("version"),
            "rejudged_at": time.time(),
            "rejudged_by": actor.id,
        },
    ]
    p = db.get(Problem, s.problem_id)
    tests = db.scalars(
        select(TestCase).where(TestCase.problem_id == p.id).order_by(TestCase.ordinal)
    ).all()
    s.problem_snapshot = {
        "version": p.version,
        "scoring": db.get(Contest, s.contest_id).scoring,
        "time_limit": p.time_limit,
        "mem_limit": p.mem_limit,
        "tests": [
            {
                "input_data": t.input_data,
                "expected": t.expected,
                "is_sample": t.is_sample,
                "weight": t.weight,
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
    s.memory_kb = 0
    s.score = 0
    db.execute(
        delete(SubmissionTestResult).where(SubmissionTestResult.submission_id == s.id)
    )
    emit(
        db,
        s.contest_id,
        "submission.rejudge",
        s.id,
        {"previous": s.history[-1]["status"]},
        actor,
    )
    return True


def capacity(db):
    pending = db.scalar(
        select(func.count())
        .select_from(Submission)
        .where(Submission.status.in_(["QUEUED", "RUNNING"]))
    )
    return max(0, int(os.getenv("MAX_QUEUE_SIZE", "200")) - pending)


def create_batch(db, c, actor, problem_id=None, affected=False):
    if db.scalar(
        select(RejudgeBatch.id).where(
            RejudgeBatch.contest_id == c.id, RejudgeBatch.finished_at.is_(None)
        )
    ):
        raise HTTPException(409, "A rejudge batch is already active")
    query = select(Submission).where(
        Submission.contest_id == c.id,
        Submission.kind == "SUBMIT",
        Submission.is_practice.is_(False),
    )
    if problem_id:
        query = query.where(Submission.problem_id == problem_id)
    rows = db.scalars(query.order_by(Submission.id)).all()
    ids = [
        s.id
        for s in rows
        if not affected
        or s.problem_snapshot.get("version") != db.get(Problem, s.problem_id).version
    ]
    batch = RejudgeBatch(
        contest_id=c.id,
        user_id=actor.id,
        remaining_ids=ids,
        total=len(ids),
        finished_at=None if ids else time.time(),
    )
    db.add(batch)
    db.flush()
    emit(
        db,
        c.id,
        "rejudge.batch",
        batch.id,
        {"total": len(ids), "problem_id": problem_id},
        actor,
    )
    return batch


def pump_batches(db):
    free = capacity(db)
    if not free:
        return
    for batch in db.scalars(
        select(RejudgeBatch)
        .where(RejudgeBatch.finished_at.is_(None))
        .order_by(RejudgeBatch.id)
    ):
        remaining = []
        for sid in batch.remaining_ids:
            s = db.get(Submission, sid)
            if s is None:
                continue
            if free <= 0 or s.status in ("QUEUED", "RUNNING"):
                remaining.append(sid)
                continue
            if reset_submission(db, s, db.get(User, batch.user_id)):
                free -= 1
        batch.remaining_ids = remaining
        if not remaining:
            batch.finished_at = time.time()
