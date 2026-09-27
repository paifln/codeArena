import time
from datetime import datetime, timezone
from sqlalchemy import select
from test_api import arena, payload, PREFIX
from app.models import (
    Contest,
    Submission,
    Team,
    TeamMember,
    User,
    ParticipationCompletion,
)
from judge.worker import claim, persist
from judge.engine import Judgement


def test_finish_waits_for_results_blocks_new_requests_and_can_reopen(
    arena, monkeypatch
):
    clients, factory, ids = arena
    monkeypatch.setenv("SUBMIT_COOLDOWN_SECONDS", "0")
    base = f"{PREFIX}/contests/{ids['contest']}"
    assert clients["teacher"].post(base + "/complete").status_code == 403
    queued = clients["student"].post(PREFIX + "/submissions", json=payload(ids))
    assert queued.status_code == 202
    assert clients["student"].post(base + "/complete").status_code == 409
    persist(factory, claim(factory), Judgement("ACCEPTED", score=100))
    result = clients["student"].post(base + "/complete")
    assert result.status_code == 200, result.text
    p = result.json()["participation"]
    assert p["solved"] == p["total"] == 1 and p["completed_at"]
    assert not result.json()["execution"]["allowed"]
    assert (
        clients["student"]
        .post(base + "/complete")
        .json()["participation"]["completed_at"]
        == p["completed_at"]
    )
    denied = clients["student"].post(PREFIX + "/submissions", json=payload(ids))
    assert (
        denied.status_code == 403
        and denied.json()["detail"] == "PARTICIPATION_COMPLETED"
    )
    reopen = base + f"/participants/u:{ids['student']}/reopen"
    assert clients["outsider"].post(reopen).status_code == 404
    assert clients["student"].post(reopen).status_code == 403
    assert clients["teacher"].post(reopen).status_code == 200
    assert (
        clients["student"].post(PREFIX + "/submissions", json=payload(ids)).status_code
        == 202
    )


def test_team_finish_applies_to_all_members(arena, monkeypatch):
    clients, factory, ids = arena
    with factory() as db:
        c = db.get(Contest, ids["contest"])
        c.mode = "TEAM"
        team = Team(contest_id=c.id, name="Shared")
        db.add(team)
        db.flush()
        for u in db.scalars(
            select(User).where(User.username.in_(["student", "otherstudent"]))
        ):
            db.add(TeamMember(contest_id=c.id, team_id=team.id, user_id=u.id))
        db.commit()
    base = f"{PREFIX}/contests/{ids['contest']}"
    question = (
        clients["student"]
        .post(base + "/clarifications", json={"question": "Can our team use zero?"})
        .json()
    )
    assert any(
        q["id"] == question["id"]
        for q in clients["otherstudent"].get(base + "/clarifications").json()
    )
    assert clients["student"].post(base + "/complete").status_code == 200
    assert clients["otherstudent"].get(base).json()["participation"]["completed_at"]
    assert (
        clients["otherstudent"]
        .post(PREFIX + "/submissions", json=payload(ids))
        .status_code
        == 403
    )
    with factory() as db:
        assert len(db.scalars(select(ParticipationCompletion)).all()) == 1
        c = db.get(Contest, ids["contest"])
        c.status = "FINISHED"
        c.practice_enabled = True
        db.commit()
    body = payload(ids)
    body["practice"] = True
    assert (
        clients["otherstudent"].post(PREFIX + "/submissions", json=body).status_code
        == 202
    )


def test_archive_restores_without_deleting_results_and_details_are_scoped(arena):
    clients, factory, ids = arena
    base = f"{PREFIX}/contests/{ids['contest']}"
    assert clients["teacher"].post(base + "/archive").status_code == 409
    with factory() as db:
        c = db.get(Contest, ids["contest"])
        c.status = "FINISHED"
        c.public_scoreboard = True
        db.commit()
    assert clients["teacher"].post(base + "/archive").status_code == 200
    assert clients["student"].get(base).status_code == 404
    assert not clients["teacher"].get(base).json()["public_scoreboard"]
    assert clients["teacher"].post(base + "/restore").status_code == 200
    assert clients["student"].get(base).status_code == 200
    details = {
        "title": "Updated title",
        "description": "New description",
        "rules": "Be kind",
    }
    assert clients["outsider"].patch(base + "/details", json=details).status_code == 404
    assert (
        clients["teacher"].patch(base + "/details", json=details).json()["rules"]
        == "Be kind"
    )
    assert clients["student"].get(base).json()["title"] == "Updated title"


def test_pause_freeze_and_early_finish_use_actual_clock(arena):
    clients, factory, ids = arena
    base = f"{PREFIX}/contests/{ids['contest']}"
    assert clients["teacher"].post(base + "/pause").status_code == 200
    assert clients["teacher"].post(base + "/freeze").status_code == 200
    assert clients["student"].get(base).json()["frozen"]
    finish = clients["teacher"].post(base + "/finish").json()
    assert finish["status"] == "FINISHED" and finish["paused_at"] is None
    assert abs(datetime.fromisoformat(finish["end_time"]).timestamp() - time.time()) < 3


def test_signed_accounts_have_separate_request_budgets(arena):
    from starlette.requests import Request
    from app.middleware.limits import request_key

    clients, _, _ = arena

    def req(token, path="/api/v1/contests"):
        return Request(
            {
                "type": "http",
                "method": "POST" if path.endswith("/login") else "GET",
                "scheme": "http",
                "path": path,
                "query_string": b"",
                "server": ("testserver", 80),
                "client": ("192.0.2.100", 1234),
                "headers": [(b"cookie", ("ca_session=" + token).encode())],
            }
        )

    a = clients["student"].cookies.get("ca_session")
    b = clients["teacher"].cookies.get("ca_session")
    assert request_key(req(a)) != request_key(req(b))
    assert request_key(req(a)).startswith("account:")
    assert request_key(req("forged")) == "ip:192.0.2.100"
    assert request_key(req(a, "/api/v1/auth/login")) == request_key(
        req(b, "/api/v1/auth/login")
    )
