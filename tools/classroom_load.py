"""Isolated classroom baseline: concurrent HTTP handlers + real Docker judge.

Does not connect to the live site or write its database. HTTP uses TestClient,
so network/TLS/browser performance is outside this measurement.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor
import json
import math
from pathlib import Path
import sys
import tempfile
import threading
import time
from http.cookies import SimpleCookie

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
from fastapi.testclient import TestClient
from fastapi import Response
from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import sessionmaker
from app.db import Base, get_db
from app.main import app
import app.security as security
from app.models import User, Problem, TestCase, Contest, ContestProblem, ContestParticipant, Submission
from judge.sandbox import DockerSandbox
from judge.worker import heartbeat, run_once
from app.operations import backup_database


def percentile(values, fraction):
    return round(sorted(values)[max(0, math.ceil(len(values)*fraction)-1)], 3) if values else None


def run(students, concurrency=2):
    from app.middleware.limits import limiter
    limiter.reset()
    sandbox = DockerSandbox()
    ready, detail = sandbox.available()
    if not ready:
        raise RuntimeError(detail)
    with tempfile.TemporaryDirectory(prefix="codearena-classroom-") as folder:
        path = Path(folder) / "load.db"
        engine = create_engine(f"sqlite:///{path.as_posix()}", connect_args={"check_same_thread":False,"timeout":30})
        @event.listens_for(engine, "connect")
        def settings(connection, _):
            connection.execute("PRAGMA foreign_keys=ON")
            connection.execute("PRAGMA journal_mode=WAL")
        Base.metadata.create_all(engine)
        factory = sessionmaker(engine, expire_on_commit=False)
        credentials = []
        with factory() as db:
            owner = User(username="owner",name="Benchmark",role="ADMIN",password_hash="not-used")
            db.add(owner);db.flush()
            problem = Problem(title="Sum",slug="sum",description="Read two integers and sum them.",difficulty="EASY",author_id=owner.id)
            contest = Contest(title="Isolated load test",author_id=owner.id,start_time=time.time()-10,end_time=time.time()+3600)
            db.add_all([problem,contest]);db.flush()
            pid,cid = problem.id,contest.id
            db.add(ContestProblem(contest_id=cid,problem_id=pid,ordinal=0))
            db.add_all([TestCase(problem_id=pid,ordinal=i,input_data=stdin,expected=output,is_sample=i==0)
                        for i,(stdin,output) in enumerate([("1 2","3"),("4 5","9")])])
            for i in range(students):
                user=User(username=f"bench{i}",name=f"Student {i}",role="STUDENT",password_hash="not-used",creator_id=owner.id)
                db.add(user);db.flush()
                response=Response()
                security.issue_session(db,response,user)
                cookies=SimpleCookie()
                for header in response.headers.getlist('set-cookie'): cookies.load(header)
                raw,csrf=cookies['ca_session'].value,cookies['ca_csrf'].value
                db.add(ContestParticipant(contest_id=cid,user_id=user.id))
                credentials.append((raw,csrf,f'192.0.2.{i+1}'))
            db.commit()
        def database():
            with factory() as db: yield db
        original=security.SessionLocal
        app.dependency_overrides[get_db]=database
        security.SessionLocal=factory
        stop=threading.Event()
        def worker():
            while not stop.is_set():
                if not run_once(factory,sandbox): stop.wait(0.1)
        heartbeat(factory,True,"isolated benchmark")
        threads=[threading.Thread(target=worker,daemon=True) for _ in range(concurrency)]
        for thread in threads: thread.start()
        def student(pair):
            raw,csrf,peer=pair
            with TestClient(app, client=(peer, 50000)) as client:
                client.cookies.set("ca_session",raw)
                client.headers["X-CSRF-Token"]=csrf
                started=time.monotonic()
                response=client.post("/api/v1/submissions",json={"contest_id":cid,"problem_id":pid,"source":"print(sum(map(int,input().split())))"})
                admission=time.monotonic()-started
                if response.status_code != 202:
                    return {"error":f"HTTP {response.status_code}","admission":admission}
                sid=response.json()["id"]
                while time.monotonic()-started < 900:
                    result=client.get(f"/api/v1/submissions/{sid}")
                    if result.status_code != 200: return {"error":f"poll HTTP {result.status_code}","admission":admission}
                    verdict=result.json()["status"]
                    if verdict not in ("QUEUED","RUNNING"):
                        return {"verdict":verdict,"admission":admission,"total":time.monotonic()-started}
                    time.sleep(1)
                return {"error":"verdict timeout","admission":admission}
        started=time.monotonic()
        try:
            with ThreadPoolExecutor(max_workers=students) as pool:
                results=list(pool.map(student,credentials))
            stop.set()
            for thread in threads: thread.join(timeout=130)
            if any(thread.is_alive() for thread in threads): raise RuntimeError("Benchmark worker did not stop")
            verified=backup_database(path,Path(folder)/"backups")
            with factory() as db:
                jobs=db.scalars(select(Submission)).all()
                queue_delays=[s.started_at-s.created_at for s in jobs if s.started_at]
            return {"students":students,"transport":"in-process HTTP TestClient","judge":"real Docker, one worker process", "concurrency":concurrency,
                "language":"Python 3.12","tests_per_submission":2,"accepted":sum(r.get("verdict")=="ACCEPTED" for r in results),
                "failures":[r for r in results if r.get("verdict")!="ACCEPTED"],
                "admission_p95_seconds":percentile([r["admission"] for r in results],.95),
                "verdict_p95_seconds":percentile([r["total"] for r in results if "total" in r],.95),
                "queue_wait_p95_seconds":percentile(queue_delays,.95),
                "duration_seconds":round(time.monotonic()-started,2),"restore_verified":verified["verified"],
                "measured_at_utc":time.strftime("%Y-%m-%dT%H:%M:%SZ",time.gmtime())}
        finally:
            stop.set()
            for thread in threads: thread.join(timeout=130)
            app.dependency_overrides.clear()
            security.SessionLocal=original
            engine.dispose()


if __name__ == "__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--students",type=int,default=30)
    parser.add_argument("--output",default="reports/classroom-load.json")
    args=parser.parse_args()
    if not 1<=args.students<=100: parser.error("students must be between 1 and 100")
    report=run(args.students)
    target=Path(args.output);target.parent.mkdir(parents=True,exist_ok=True)
    target.write_text(json.dumps(report,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(report,indent=2))
    sys.exit(bool(report["failures"]))
