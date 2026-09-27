"""Real-browser smoke on an isolated database. Requires pip install playwright.

Uses installed Microsoft Edge, local built frontend and a disposable API process.
Never connects to the deployed database or creates accounts in the live site.
"""

import json
import os
from pathlib import Path
import secrets
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / "artifacts" / "contest-ui"
ARTIFACTS.mkdir(parents=True, exist_ok=True)


def run():
    from playwright.sync_api import sync_playwright

    with tempfile.TemporaryDirectory(prefix="codearena-browser-") as folder:
        os.environ["DATABASE_URL"] = (
            "sqlite:///" + (Path(folder) / "arena.db").as_posix()
        )
        os.environ["SECRET_KEY"] = secrets.token_hex(64)
        os.environ["COOKIE_SECURE"] = "false"
        os.environ["CODEARENA_LAN_HOST"] = "192.168.1.34"
        sys.path.insert(0, str(ROOT / "backend"))
        from app.db import Base, engine, SessionLocal
        from app.models import (
            User,
            Problem,
            TestCase,
            Contest,
            ContestProblem,
            Team,
            TeamMember,
            Submission,
            SystemSetting,
            Group,
            GroupMember,
        )
        from app.security import hash_password
        from app.services.contest_events import judged

        Base.metadata.create_all(engine)
        password = secrets.token_urlsafe(18)
        hashed = hash_password(password)
        now = time.time()
        with SessionLocal() as db:
            admin = User(
                username="organizer",
                name="Contest Organizer",
                role="ADMIN",
                password_hash=hashed,
            )
            db.add(admin)
            db.flush()
            contest = Contest(
                title="CodeArena Campus Cup",
                description="Local programming contest",
                author_id=admin.id,
                mode="TEAM",
                start_time=now - 7200,
                end_time=now - 20,
                status="FINISHED",
                freeze_at=now - 1800,
                public_scoreboard=True,
            )
            group = Group(name="Contest participants", author_id=admin.id)
            db.add_all([contest, group])
            db.flush()
            cid = contest.id
            problems = []
            for i, title in enumerate(
                [
                    "Two Sum",
                    "Lost Routes",
                    "Balanced Trees",
                    "Signal",
                    "Segments",
                    "Final Code",
                ]
            ):
                p = Problem(
                    title=title,
                    slug=f"problem-{i}",
                    description="Read two integers and print their sum.",
                    difficulty="EASY",
                    author_id=admin.id,
                )
                db.add(p)
                db.flush()
                problems.append(p)
                db.add(ContestProblem(contest_id=cid, problem_id=p.id, ordinal=i))
                db.add(
                    TestCase(
                        problem_id=p.id,
                        ordinal=0,
                        input_data="1 2",
                        expected="3",
                        is_sample=True,
                    )
                )
            for i, name in enumerate(
                [
                    "segfault.exe",
                    "ZKU Overflow",
                    "Binary Search",
                    "Stack Masters",
                    "Null Pointers",
                    "Green Threads",
                ]
            ):
                user = User(
                    username=f"team{i}",
                    name=f"Participant {i + 1}",
                    role="STUDENT",
                    creator_id=admin.id,
                    password_hash=hashed,
                )
                team = Team(contest_id=cid, name=name, organization="ZKU")
                db.add_all([user, team])
                db.flush()
                db.add(TeamMember(contest_id=cid, team_id=team.id, user_id=user.id))
                db.add(GroupMember(group_id=group.id, user_id=user.id))
                for j in range(6 - i):
                    created = now - 6000 + i * 600 + j * 800
                    s = Submission(
                        user_id=user.id,
                        team_id=team.id,
                        contest_id=cid,
                        problem_id=problems[j].id,
                        source="print(3)",
                        language="python3",
                        kind="SUBMIT",
                        status="ACCEPTED",
                        score=100,
                        created_at=created,
                        started_at=created + 1,
                        finished_at=created + 2,
                        contest_elapsed=created - contest.start_time,
                        problem_snapshot={"version": 1, "tests": []},
                    )
                    db.add(s)
                    db.flush()
                    judged(db, s)
            db.add(
                SystemSetting(
                    key="judge_heartbeat",
                    value={"time": time.time(), "available": True, "slots": 2},
                )
            )
            db.commit()
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            port = sock.getsockname()[1]
        base = f"http://127.0.0.1:{port}"
        env = dict(os.environ, PYTHONPATH=str(ROOT / "backend"))
        with (ARTIFACTS / "api.log").open("w", encoding="utf-8") as log:
            server = subprocess.Popen(
                [
                    sys.executable,
                    "-m",
                    "uvicorn",
                    "app.main:app",
                    "--host",
                    "127.0.0.1",
                    "--port",
                    str(port),
                ],
                cwd=ROOT / "backend",
                env=env,
                stdout=log,
                stderr=log,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            try:
                for _ in range(100):
                    try:
                        urllib.request.urlopen(
                            base + "/api/v1/health", timeout=1
                        ).close()
                        break
                    except Exception:
                        time.sleep(0.1)
                with sync_playwright() as p:
                    browser = p.chromium.launch(channel="msedge", headless=True)
                    context = browser.new_context(
                        viewport={"width": 1440, "height": 1000}
                    )
                    context.add_init_script("localStorage.setItem('ca_language','en')")
                    page = context.new_page()
                    errors = []
                    page.on("pageerror", lambda error: errors.append(str(error)))
                    page.goto(base)
                    page.locator("input[name=username]").fill("organizer")
                    page.locator("input[name=password]").fill(password)
                    page.locator(".auth-form form button[type=submit]").click()
                    page.locator(".sidebar").wait_for()
                    page.goto(base + f"/contests/{cid}/control")
                    page.get_by_role(
                        "heading", name="CodeArena Campus Cup", exact=True
                    ).wait_for()
                    page.screenshot(
                        path=str(ARTIFACTS / "control-desktop.png"), full_page=True
                    )
                    page.get_by_role("button", name="Settings", exact=True).click()
                    page.locator(".lan-qr svg").wait_for()
                    page.screenshot(
                        path=str(ARTIFACTS / "settings-qr.png"), full_page=True
                    )
                    page.get_by_role(
                        "button", name="Contest replay", exact=True
                    ).click()
                    page.locator(".replay-controls").wait_for()
                    page.screenshot(path=str(ARTIFACTS / "replay.png"), full_page=True)
                    page.goto(base + "/contests")
                    page.get_by_role(
                        "button", name="Create contest", exact=True
                    ).click()
                    page.locator(".contest-wizard").wait_for()
                    page.screenshot(path=str(ARTIFACTS / "wizard.png"), full_page=True)
                    page.goto(base + "/problems")
                    page.get_by_role("button", name="Edit", exact=True).first.click()
                    page.get_by_label(
                        "Statement attachments", exact=True
                    ).set_input_files(
                        {
                            "name": "statement.pdf",
                            "mimeType": "application/pdf",
                            "buffer": b"%PDF-1.4\nBrowser attachment fixture\n%%EOF\n",
                        }
                    )
                    page.get_by_role(
                        "link", name="statement.pdf", exact=False
                    ).wait_for()
                    with page.expect_download() as downloaded:
                        page.get_by_role(
                            "link", name="statement.pdf", exact=False
                        ).click()
                    assert downloaded.value.suggested_filename == "statement.pdf"
                    page.screenshot(
                        path=str(ARTIFACTS / "problem-documents.png"), full_page=True
                    )
                    page.get_by_role("button", name="Close", exact=True).click()
                    page.get_by_role(
                        "button", name="Import from URL", exact=True
                    ).click()
                    page.locator("input[type=url]").fill(
                        "https://codeforces.com/problemset/problem/4/A"
                    )
                    fixture = b'<div class="problem-statement"><div class="title">Imported local sum</div><p>Add two integers.</p><div class="sample-test"><div class="input"><pre>1 2</pre></div><div class="output"><pre>3</pre></div></div></div>'
                    page.locator("input[type=file]").set_input_files(
                        {
                            "name": "problem.html",
                            "mimeType": "text/html",
                            "buffer": fixture,
                        }
                    )
                    page.get_by_role("button", name="Preview", exact=True).click()
                    page.locator("input[name=title]").wait_for()
                    assert (
                        page.locator("input[name=title]").input_value()
                        == "Imported local sum"
                    )
                    page.screenshot(
                        path=str(ARTIFACTS / "problem-import.png"), full_page=True
                    )
                    page.get_by_role("button", name="Save", exact=True).click()
                    page.get_by_text("Imported local sum", exact=True).wait_for()
                    mobile = context.new_page()
                    mobile.set_viewport_size({"width": 390, "height": 844})
                    mobile.goto(base + f"/contests/{cid}/puzzles")
                    mobile.locator(".delivery-card").first.wait_for()
                    mobile.screenshot(
                        path=str(ARTIFACTS / "puzzle-mobile.png"), full_page=True
                    )
                    mobile.locator(".delivery-card button").first.click()
                    mobile.get_by_role(
                        "button", name="Delivered", exact=True
                    ).first.wait_for()
                    public = browser.new_context(
                        viewport={"width": 1920, "height": 1080}
                    )
                    display = public.new_page()
                    display.goto(base + f"/display/contests/{cid}/scoreboard")
                    display.locator(".professional-board").wait_for()
                    assert display.locator(".sidebar").count() == 0
                    display.screenshot(
                        path=str(ARTIFACTS / "public-scoreboard.png"), full_page=True
                    )
                    display.goto(base + f"/display/contests/{cid}/puzzles")
                    display.locator(".puzzle-gallery").wait_for()
                    display.screenshot(
                        path=str(ARTIFACTS / "public-puzzles.png"), full_page=True
                    )
                    assert not errors, errors
                    print(
                        json.dumps(
                            {
                                "browser": "Microsoft Edge",
                                "isolated": True,
                                "page_errors": errors,
                                "screenshots": 9,
                            }
                        )
                    )
                    browser.close()
            finally:
                server.terminate()
                server.wait(timeout=15)
                engine.dispose()
                import gc

                gc.collect()


if __name__ == "__main__":
    run()
