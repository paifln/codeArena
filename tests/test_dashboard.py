"""Dashboard aggregates must not depend on pagination or include sample runs."""

from test_api import arena, PREFIX
from app.models import Submission


def test_dashboard_and_global_submission_scope(arena):
    clients, sessions, ids = arena
    with sessions() as db:
        for kind, verdict in [
            ("RUN", "ACCEPTED"),
            ("SUBMIT", "ACCEPTED"),
            ("SUBMIT", "WRONG_ANSWER"),
        ]:
            db.add(
                Submission(
                    user_id=ids["student"],
                    problem_id=ids["problem"],
                    contest_id=ids["contest"],
                    source="print(3)",
                    kind=kind,
                    status=verdict,
                    problem_snapshot={"tests": []},
                )
            )
        db.commit()
    stats = clients["teacher"].get(PREFIX + "/dashboard").json()
    assert stats["submissions"] == 2
    assert stats["accepted"] == 1
    assert stats["acceptance_rate"] == 50
    assert len(clients["teacher"].get(PREFIX + "/submissions").json()) == 3
    assert clients["outsider"].get(PREFIX + "/submissions").json() == []
    assert clients["outsider"].get(PREFIX + "/dashboard").json()["submissions"] == 0
    assert clients["otherstudent"].get(PREFIX + "/submissions").json() == []
    assert clients["student"].get(PREFIX + "/dashboard").json()["accepted"] == 1
