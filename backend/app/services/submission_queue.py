import os
import time
from fastapi import HTTPException
from sqlalchemy import select, func
from ..db import lock_write
from ..models import Submission, ContestProblem, Problem, TestCase
from ..security import throttle
from .access import access_contest
from .common import audit
from .execution import execution_policy


def enqueue_submission(db, req, user):
    lock_write(db)
    c = access_contest(db, req.contest_id, user)
    if req.request_id:
        existing = db.scalar(
            select(Submission).where(
                Submission.user_id == user.id,
                Submission.request_id == str(req.request_id),
            )
        )
        if existing:
            fields = (
                "contest_id",
                "problem_id",
                "source",
                "kind",
                "language",
                "custom_input",
            )
            if any(getattr(existing, key) != getattr(req, key) for key in fields):
                raise HTTPException(409, "IDEMPOTENCY_CONFLICT")
            return existing
    policy = execution_policy(db, c)
    if not policy["allowed"]:
        raise HTTPException(
            503 if policy["reason"] == "JUDGE_UNAVAILABLE" else 403, policy["reason"]
        )
    if not db.get(ContestProblem, (c.id, req.problem_id)):
        raise HTTPException(404, "Problem not found")
    p = db.get(Problem, req.problem_id)
    if req.kind == "SUBMIT" and req.custom_input is not None:
        raise HTTPException(422, "Custom input is only allowed for Run")
    throttle(
        db,
        f"{req.kind}:{user.id}",
        1,
        float(os.getenv(req.kind + "_COOLDOWN_SECONDS", "3")),
    )
    pending = db.scalar(
        select(func.count())
        .select_from(Submission)
        .where(Submission.status.in_(["QUEUED", "RUNNING"]))
    )
    if pending >= int(os.getenv("MAX_QUEUE_SIZE", "200")):
        raise HTTPException(429, "Judge queue is full. Try again shortly.")
    own_pending = db.scalar(
        select(func.count())
        .select_from(Submission)
        .where(
            Submission.user_id == user.id, Submission.status.in_(["QUEUED", "RUNNING"])
        )
    )
    if own_pending >= 3:
        raise HTTPException(429, "Wait for your pending submissions")
    tests = db.scalars(
        select(TestCase).where(TestCase.problem_id == p.id).order_by(TestCase.ordinal)
    ).all()
    selected = [
        {"input_data": t.input_data, "expected": t.expected, "is_sample": t.is_sample}
        for t in tests
        if req.kind == "SUBMIT" or t.is_sample
    ]
    snapshot = {
        "tests": selected,
        "time_limit": p.time_limit,
        "mem_limit": p.mem_limit,
        "version": p.version,
    }
    s = Submission(
        request_id=str(req.request_id) if req.request_id else None,
        user_id=user.id,
        contest_id=c.id,
        problem_id=p.id,
        source=req.source,
        language=req.language,
        kind=req.kind,
        custom_input=req.custom_input,
        problem_snapshot=snapshot,
        status="QUEUED",
        contest_elapsed=max(0, time.time() - c.start_time - c.paused_seconds),
    )
    db.add(s)
    db.flush()
    audit(db, user, "submission.created", s.id)
    db.commit()
    return s
