import time
from sqlalchemy import select
from test_api import arena, payload, PREFIX
from app.models import (
    Contest,
    Submission,
    PuzzleReward,
    RejudgeBatch,
    AuditLog,
    ContestPresence,
    User,
)
from app.services.contest_events import reconcile_rewards, lifecycle
from app.services.rejudging import pump_batches, reset_submission
from judge.worker import claim, persist
from judge.engine import Judgement


def accepted(clients, factory, ids):
    response = clients["student"].post(PREFIX + "/submissions", json=payload(ids))
    assert response.status_code == 202, response.text
    job = claim(factory)
    assert persist(factory, job, Judgement("ACCEPTED", score=100))
    return job["id"]


def test_freeze_public_display_reveal_and_reward_deduplication(arena, monkeypatch):
    clients, factory, ids = arena
    monkeypatch.setenv("SUBMIT_COOLDOWN_SECONDS", "0")
    path = f"{PREFIX}/public/contests/{ids['contest']}/scoreboard"
    assert clients["student"].get(path).status_code == 404
    with factory() as db:
        c = db.get(Contest, ids["contest"])
        c.freeze_at = time.time() - 1
        c.public_scoreboard = True
        db.commit()
    accepted(clients, factory, ids)
    accepted(clients, factory, ids)
    public = clients["student"].get(path).json()
    assert all(r["solved"] == 0 for r in public["rows"])
    assert sum(x["pending"] for r in public["rows"] for x in r["cells"]) == 2
    assert all("source" not in str(r) for r in public["rows"])
    desk = f"{PREFIX}/contests/{ids['contest']}/puzzles"
    assert clients["student"].get(desk).status_code == 403
    assert clients["outsider"].get(desk).status_code == 404
    rewards = clients["teacher"].get(desk).json()
    assert len(rewards) == 1
    for _ in range(2):
        assert (
            clients["teacher"]
            .post(f"{PREFIX}/puzzles/{rewards[0]['id']}/delivered")
            .status_code
            == 200
        )
    with factory() as db:
        assert db.get(PuzzleReward, rewards[0]["id"]).delivered_by is not None
        db.get(Contest, ids["contest"]).status = "FINISHED"
        db.commit()
    reveal = f"{PREFIX}/contests/{ids['contest']}/reveal"
    assert clients["outsider"].post(reveal).status_code == 404
    result = clients["teacher"].post(reveal)
    assert result.status_code == 200, result.text
    assert sum(r["solved"] for r in clients["student"].get(path).json()["rows"]) == 1
    assert clients["teacher"].post(reveal).json()["done"]


def test_rejudge_revokes_piece_but_keeps_delivery_history(arena, monkeypatch):
    clients, factory, ids = arena
    accepted(clients, factory, ids)
    with factory() as db:
        reward = db.scalar(select(PuzzleReward))
        rid = reward.id
        reward.delivered_at = time.time()
        reward.delivered_by = 1
        actor = db.scalar(select(User).where(User.username == "teacher"))
        reset_submission(db, db.scalar(select(Submission)), actor)
        db.commit()
    job = claim(factory)
    persist(factory, job, Judgement("WRONG_ANSWER"))
    with factory() as db:
        reward = db.get(PuzzleReward, rid)
        assert reward.revoked and reward.delivered_at
        reset_submission(
            db,
            db.scalar(select(Submission)),
            db.scalar(select(User).where(User.username == "teacher")),
        )
        db.commit()
    job = claim(factory)
    persist(factory, job, Judgement("ACCEPTED", score=100))
    with factory() as db:
        rewards = db.scalars(select(PuzzleReward)).all()
        assert len(rewards) == 1 and not rewards[0].revoked and rewards[0].delivered_at


def test_historical_replay_keeps_prior_verdict_and_never_enqueues(arena):
    clients, factory, ids = arena
    sid = accepted(clients, factory, ids)
    with factory() as db:
        c = db.get(Contest, ids["contest"])
        c.status = "FINISHED"
        s = db.get(Submission, sid)
        s.created_at = c.start_time + 10
        s.finished_at = c.start_time + 20
        s.contest_elapsed = 10
        s.history = [
            {"status": "WRONG_ANSWER", "score": 0, "finished_at": c.start_time + 15}
        ]
        db.commit()
    path = f"{PREFIX}/contests/{ids['contest']}/replay"
    earlier = clients["teacher"].get(path + "?elapsed=16").json()["board"]
    later = clients["teacher"].get(path + "?elapsed=21").json()["board"]
    assert sum(r["solved"] for r in earlier["rows"]) == 0
    assert sum(r["solved"] for r in later["rows"]) == 1
    with factory() as db:
        assert db.get(Submission, sid).status == "ACCEPTED"
        db.get(Contest, ids["contest"]).freeze_at = time.time() - 1
        db.commit()
    assert clients["student"].get(path).status_code == 403


def test_bulk_rejudge_drains_without_exceeding_queue(arena, monkeypatch):
    clients, factory, ids = arena
    monkeypatch.setenv("SUBMIT_COOLDOWN_SECONDS", "0")
    accepted(clients, factory, ids)
    accepted(clients, factory, ids)
    monkeypatch.setenv("MAX_QUEUE_SIZE", "1")
    path = f"{PREFIX}/contests/{ids['contest']}/rejudge"
    assert clients["student"].post(path, json={}).status_code == 403
    assert clients["teacher"].post(path, json={}).json()["total"] == 2
    assert clients["teacher"].post(path, json={}).status_code == 409
    with factory() as db:
        pump_batches(db)
        db.commit()
        assert len(db.scalar(select(RejudgeBatch)).remaining_ids) == 1
    job = claim(factory)
    persist(factory, job, Judgement("ACCEPTED", score=100))
    with factory() as db:
        pump_batches(db)
        db.commit()
        batch = db.scalar(select(RejudgeBatch))
        assert batch.finished_at and not batch.remaining_ids


def test_presence_clarification_status_and_control_permissions(arena):
    clients, factory, ids = arena
    base = f"{PREFIX}/contests/{ids['contest']}"
    assert clients["student"].get(base + "/control").status_code == 403
    assert clients["outsider"].get(base + "/control").status_code == 404
    assert clients["student"].post(base + "/presence").status_code == 200
    with factory() as db:
        db.scalar(select(ContestPresence)).last_seen = time.time() - 120
        lifecycle(db)
        db.commit()
        assert db.scalar(select(AuditLog).where(AuditLog.action == "team.disconnected"))
    question = (
        clients["student"]
        .post(
            base + "/clarifications",
            json={"question": "Is zero valid?", "problem_id": ids["problem"]},
        )
        .json()
    )
    assert (
        clients["teacher"]
        .post(f"{PREFIX}/clarifications/{question['id']}/dismiss")
        .status_code
        == 200
    )
    assert (
        clients["student"].get(base + "/clarifications").json()[0]["status"]
        == "DISMISSED"
    )
    assert clients["teacher"].get(base + "/control").status_code == 200


def test_logo_and_csv_are_scoped_and_validated(arena):
    clients, _, ids = arena
    logo = f"{PREFIX}/contests/{ids['contest']}/logo"
    assert clients["student"].post(logo, json={"data": ""}).status_code == 403
    assert (
        clients["teacher"]
        .post(logo, json={"data": "data:image/svg+xml;base64,AAAA"})
        .status_code
        == 422
    )
    assert clients["teacher"].post(logo, json={"data": ""}).status_code == 200
    assert (
        clients["teacher"]
        .post(PREFIX + "/teams/prepare", json={"csv": "wrong,columns\na,b"})
        .status_code
        == 422
    )
    result = clients["teacher"].post(
        PREFIX + "/teams/prepare",
        json={
            "csv": "team_name,organization,member1,member2,member3\nAlpha,ZKU,Alice,Bob,\n"
        },
    )
    assert result.status_code == 201, result.text
    assert (
        len(result.json()["credentials"]) == 2
        and len(result.json()["teams"][0]["user_ids"]) == 2
    )


def test_pending_rejudge_preserves_piece_and_startup_is_idempotent(arena):
    clients, factory, ids = arena
    sid = accepted(clients, factory, ids)
    with factory() as db:
        c = db.get(Contest, ids["contest"])
        actor = db.scalar(select(User).where(User.username == "teacher"))
        reset_submission(db, db.get(Submission, sid), actor)
        reconcile_rewards(db, c)
        lifecycle(db)
        db.commit()
        lifecycle(db)
        db.commit()
        rewards = db.scalars(select(PuzzleReward)).all()
        assert len(rewards) == 1 and not rewards[0].revoked
        markers = db.scalars(
            select(AuditLog).where(AuditLog.action == "puzzle.initialized")
        ).all()
        assert len(markers) == 1


def test_future_freeze_and_disabled_language(arena):
    clients, factory, ids = arena
    with factory() as db:
        c = db.get(Contest, ids["contest"])
        c.freeze_at = time.time() + 300
        c.public_scoreboard = True
        c.languages = ["cpp20"]
        db.commit()
    rejected = clients["student"].post(PREFIX + "/submissions", json=payload(ids))
    assert rejected.status_code == 422
    with factory() as db:
        db.get(Contest, ids["contest"]).languages = ["python3"]
        db.commit()
    accepted(clients, factory, ids)
    board = (
        clients["student"]
        .get(f"{PREFIX}/public/contests/{ids['contest']}/scoreboard")
        .json()
    )
    assert not board["frozen"]
    assert sum(row["solved"] for row in board["rows"]) == 1


def test_public_websocket_hides_frozen_verdict_and_revokes_access(arena):
    import pytest
    from starlette.websockets import WebSocketDisconnect

    clients, factory, ids = arena
    with factory() as db:
        c = db.get(Contest, ids["contest"])
        c.public_scoreboard = True
        c.freeze_at = time.time() - 1
        db.commit()
    response = clients["student"].post(PREFIX + "/submissions", json=payload(ids))
    assert response.status_code == 202
    path = f"/ws/public/contests/{ids['contest']}"
    with pytest.raises(WebSocketDisconnect):
        with clients["student"].websocket_connect(
            path, headers={"Origin": "http://evil.invalid"}
        ):
            pass
    with clients["student"].websocket_connect(
        path, headers={"Origin": "http://testserver"}
    ) as ws:
        before = ws.receive_json()
        job = claim(factory)
        assert persist(factory, job, Judgement("ACCEPTED", score=100))
        assert ws.receive_json() == before
        assert list(before) == ["revision"]
        with factory() as db:
            db.get(Contest, ids["contest"]).public_scoreboard = False
            db.commit()
        with pytest.raises(WebSocketDisconnect):
            ws.receive_json()
