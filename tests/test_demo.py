from sqlalchemy import create_engine, select, func
from sqlalchemy.orm import sessionmaker
from app.db import Base
from app.demo import create_demo
from app.models import User, Contest, ContestProblem, TestCase as ProblemTest


def test_demo_is_one_draft_and_does_not_create_users(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'demo.db'}")
    Base.metadata.create_all(engine)
    factory = sessionmaker(engine)
    with factory() as db:
        db.add(
            User(username="owner", name="Owner", password_hash="unused", role="ADMIN")
        )
        db.commit()
    with factory() as db:
        first, created = create_demo(db, 1)
        assert created
    with factory() as db:
        second, created = create_demo(db, 1)
        assert not created and first == second
        assert db.scalar(select(func.count()).select_from(Contest)) == 1
        assert db.scalar(select(func.count()).select_from(User)) == 1
        assert db.scalar(select(func.count()).select_from(ContestProblem)) == 3
        assert db.scalar(select(func.count()).select_from(ProblemTest)) == 15
        contest = db.get(Contest, first)
        assert contest.status == "DRAFT"
        assert contest.end_time - contest.start_time == 5400
    engine.dispose()
