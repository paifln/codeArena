"""Single durable SQLite queue owner; atomic leases also prevent duplicate claims.

Run with PYTHONPATH=backend python -m judge.worker. Do not run this in the API.
"""
import logging
import signal
import time
import uuid
from sqlalchemy import delete, select, update
from app.db import SessionLocal
from app.models import Submission, SubmissionTestResult, SystemSetting
from .engine import Judgement, judge
from .limits import LEASE_SECONDS
from .sandbox import DockerSandbox
from .verdicts import Verdict

log = logging.getLogger('codearena.judge')


def heartbeat(factory, available, detail):
    with factory() as db:
        # Pulse and the queue loop can start concurrently. Serialize the initial
        # read/insert on SQLite; use a native conflict update on PostgreSQL.
        if db.get_bind().dialect.name == 'sqlite':
            from sqlalchemy import text
            db.execute(text('BEGIN IMMEDIATE'))
        elif db.get_bind().dialect.name == 'postgresql':
            from sqlalchemy.dialects.postgresql import insert
            value = {'time': time.time(), 'available': available, 'detail': detail}
            statement = insert(SystemSetting).values(key='judge_heartbeat', value=value)
            db.execute(statement.on_conflict_do_update(index_elements=['key'], set_={'value': value}))
            db.commit()
            return
        record = db.get(SystemSetting, 'judge_heartbeat')
        value = {'time': time.time(), 'available': available, 'detail': detail}
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
        return {'id': row.id, 'lease_token': token, 'source': row.source,
                'language': row.language, 'snapshot': row.problem_snapshot,
                'kind': row.kind, 'custom_input': row.custom_input}


def persist(factory, job, result):
    with factory() as db:
        changed = db.execute(update(Submission).where(Submission.id == job['id'],
                             Submission.status == 'RUNNING', Submission.lease_token == job['lease_token'])
                             .values(status=str(result.verdict), finished_at=time.time(), lease_token=None,
                                     time_ms=result.time_ms, memory_kb=result.memory_kb, error=result.error)).rowcount
        if not changed:
            db.rollback()
            return False  # A rejudge or recovered lease superseded this worker.
        db.execute(delete(SubmissionTestResult).where(SubmissionTestResult.submission_id == job['id']))
        for item in result.tests:
            db.add(SubmissionTestResult(submission_id=job['id'], **item))
        db.commit()
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
    logging.basicConfig(level=logging.INFO)
    stopped = threading.Event()
    signal.signal(signal.SIGTERM, lambda *_: stopped.set())
    signal.signal(signal.SIGINT, lambda *_: stopped.set())
    sandbox = DockerSandbox()

    def pulse():
        while not stopped.is_set():
            try:
                ready, detail = sandbox.available()
                heartbeat(SessionLocal, ready, detail)
                if ready:
                    sandbox.cleanup_expired()
            except Exception:
                log.exception('Judge heartbeat failed')
            stopped.wait(5)
    threading.Thread(target=pulse, daemon=True).start()
    try:
        while not stopped.is_set():
            try:
                if not run_once(SessionLocal, sandbox):
                    stopped.wait(2)
            except Exception:
                log.exception('Queue unavailable; waiting before retry')
                stopped.wait(5)
    finally:
        stopped.set()
        heartbeat(SessionLocal, False, 'Judge worker stopped')


if __name__ == '__main__':
    main()
