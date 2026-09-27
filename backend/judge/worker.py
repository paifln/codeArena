"""Single durable SQLite queue owner; atomic leases also prevent duplicate claims.

Run with PYTHONPATH=backend python -m judge.worker. Do not run this in the API.
"""
import os
import logging
import signal
import time
import uuid
from sqlalchemy import delete, select, update
from app.db import SessionLocal
from app.models import Submission, SubmissionTestResult, SystemSetting
from app.middleware.logging import configure_logging, event
from app.services.contest_events import judged, lifecycle
from app.services.rejudging import pump_batches
from .engine import Judgement, judge
from .limits import LEASE_SECONDS
from .sandbox import DockerSandbox
from .verdicts import Verdict

log = logging.getLogger('codearena.judge')


def heartbeat(factory, available, detail):
    with factory() as db:
        # Pulse and the queue loop can start concurrently. Serialize the initial
        # read/insert on SQLite.
        if db.get_bind().dialect.name == 'sqlite':
            from sqlalchemy import text
            db.execute(text('BEGIN IMMEDIATE'))
        record = db.get(SystemSetting, 'judge_heartbeat')
        value = {'time': time.time(), 'available': available, 'detail': detail, 'slots':max(1,min(4,int(os.getenv('JUDGE_CONCURRENCY','2'))))}
        if record is None:
            db.add(SystemSetting(key='judge_heartbeat', value=value))
        else:
            record.value = value
        db.commit()


def recover_stale(factory, now=None):
    now = time.time() if now is None else now
    with factory() as db:
        stale = (Submission.status == 'RUNNING', Submission.started_at < now - LEASE_SECONDS)
        # A repeatedly crashing job must not starve the queue forever.
        failed = db.execute(update(Submission).where(*stale, Submission.attempt_count >= 3).values(
            status='SYSTEM_ERROR', finished_at=now, lease_token=None,
            error='Judge interrupted repeatedly; teacher may retry')).rowcount
        recovered = db.execute(update(Submission).where(*stale, Submission.attempt_count < 3).values(
            status='QUEUED', started_at=None, lease_token=None)).rowcount
        db.commit()
        if recovered or failed:
            event("queue.recovered", recovered=recovered, failed=failed)
        return recovered + failed


def claim(factory):
    with factory() as db:
        candidate = db.scalar(select(Submission.id).where(Submission.status == 'QUEUED')
                              .order_by(Submission.created_at, Submission.id).limit(1))
        if candidate is None:
            return None
        token = uuid.uuid4().hex
        changed = db.execute(update(Submission).where(Submission.id == candidate,
                             Submission.status == 'QUEUED').values(status='RUNNING',
                             started_at=time.time(), lease_token=token,
                             attempt_count=Submission.attempt_count + 1)).rowcount
        db.commit()
        if not changed:
            return None
        row = db.get(Submission, candidate)
        event("queue.claimed", submission_id=row.id)
        return {'id': row.id, 'lease_token': token, 'source': row.source,
                'language': row.language, 'snapshot': row.problem_snapshot,
                'kind': row.kind, 'custom_input': row.custom_input}


def persist(factory, job, result):
    with factory() as db:
        changed = db.execute(update(Submission).where(Submission.id == job['id'],
                             Submission.status == 'RUNNING', Submission.lease_token == job['lease_token'])
                             .values(status=str(result.verdict), finished_at=time.time(), lease_token=None,
                                     time_ms=result.time_ms, memory_kb=result.memory_kb, error=result.error, score=result.score)).rowcount
        if not changed:
            db.rollback()
            return False  # A rejudge or recovered lease superseded this worker.
        db.execute(delete(SubmissionTestResult).where(SubmissionTestResult.submission_id == job['id']))
        for item in result.tests:
            db.add(SubmissionTestResult(submission_id=job['id'], **item))
        db.flush()
        judged(db,db.get(Submission,job['id']))
        db.commit()
        event("judge.verdict", submission_id=job['id'], verdict=str(result.verdict), score=result.score)
        return True


def run_once(factory=SessionLocal, sandbox=None):
    sandbox = sandbox or DockerSandbox()
    available, detail = sandbox.available()
    heartbeat(factory, available, detail)
    recover_stale(factory)
    if not available:
        return False
    job = claim(factory)
    if job is None:
        return False
    try:
        result = judge(job['source'], job['language'], job['snapshot'],
                       job['kind'], job['custom_input'], sandbox)
    except Exception:
        log.exception('Unexpected judge failure for submission %s', job['id'])
        result = Judgement(Verdict.SYSTEM_ERROR, error='Judge failed; teacher may safely retry')
    persist(factory, job, result)
    return True


def main():
    import threading
    configure_logging()
    stopped = threading.Event()
    signal.signal(signal.SIGTERM, lambda *_: stopped.set())
    signal.signal(signal.SIGINT, lambda *_: stopped.set())
    sandbox = DockerSandbox()

    def pulse():
        while not stopped.is_set():
            try:
                ready, detail = sandbox.available()
                heartbeat(SessionLocal, ready, detail)
                with SessionLocal() as db:
                    from app.db import lock_write
                    lock_write(db)
                    lifecycle(db)
                    if ready: pump_batches(db)
                    db.commit()
                if ready:
                    sandbox.cleanup_expired()
            except Exception:
                log.exception('Judge heartbeat failed')
            stopped.wait(5)
    threading.Thread(target=pulse, daemon=True).start()
    def consume():
        while not stopped.is_set():
            try:
                if not run_once(SessionLocal, sandbox):
                    stopped.wait(0.5)
            except Exception:
                log.exception('Queue unavailable; waiting before retry')
                stopped.wait(5)
    count = max(1, min(4, int(os.environ.get('JUDGE_CONCURRENCY', '2'))))
    consumers = [threading.Thread(target=consume, daemon=True) for _ in range(count)]
    for consumer in consumers:
        consumer.start()
    try:
        while not stopped.wait(1):
            pass
    finally:
        stopped.set()
        for consumer in consumers:
            consumer.join(timeout=125)
        heartbeat(SessionLocal, False, 'Judge worker stopped')



if __name__ == '__main__':
    main()
