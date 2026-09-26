import sys
import time
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'backend'))
from app.db import Base
from app.models import User, Problem, Contest, ContestProblem, ContestParticipant, Submission
from app.services import scoreboard


@pytest.fixture
def arena(tmp_path):
    engine = create_engine(f'sqlite:///{(tmp_path / "scoreboard.db").as_posix()}')
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        teacher = User(username='teacher', name='Teacher', password_hash='not-a-real-password', role='TEACHER')
        student = User(username='student', name='Student', password_hash='not-a-real-password', role='STUDENT')
        db.add_all([teacher, student]); db.flush()
        problem = Problem(title='Sum', slug='sum', description='Sum two integers', difficulty='EASY', author_id=teacher.id)
        contest = Contest(title='Arena', author_id=teacher.id, start_time=time.time()-3600, end_time=time.time()+3600)
        db.add_all([problem, contest]); db.flush()
        db.add_all([ContestProblem(contest_id=contest.id, problem_id=problem.id, ordinal=0), ContestParticipant(contest_id=contest.id, user_id=student.id)])
        db.commit()
        yield db, teacher, student, problem, contest
    engine.dispose()


def submission(db, student, problem, contest, verdict, minute, **kwargs):
    timestamp = contest.start_time + minute*60
    item = Submission(user_id=student.id, problem_id=problem.id, contest_id=contest.id,
                      source='print(3)', problem_snapshot={}, status=verdict,
                      contest_elapsed=minute*60, created_at=timestamp, finished_at=timestamp+1, **kwargs)
    db.add(item); db.commit()
    return item


def test_icpc_excludes_runs_system_errors_and_attempts_after_acceptance(arena):
    db, teacher, student, problem, contest = arena
    submission(db, student, problem, contest, 'WRONG_ANSWER', 1, kind='RUN')
    submission(db, student, problem, contest, 'SYSTEM_ERROR', 2)
    submission(db, student, problem, contest, 'WRONG_ANSWER', 3)
    submission(db, student, problem, contest, 'ACCEPTED', 5)
    submission(db, student, problem, contest, 'WRONG_ANSWER', 6)
    row = scoreboard(db, contest, student)['rows'][0]
    assert row['solved'] == 1
    assert row['penalty'] == 25
    assert row['cells'][0]['attempts'] == 1


def test_freeze_hides_later_results_from_students_only(arena):
    db, teacher, student, problem, contest = arena
    submission(db, student, problem, contest, 'WRONG_ANSWER', 2)
    submission(db, student, problem, contest, 'ACCEPTED', 5)
    contest.freeze_at = contest.start_time + 4*60
    db.commit()
    public = scoreboard(db, contest, student)
    assert public['frozen'] is True
    assert public['rows'][0]['solved'] == 0
    assert scoreboard(db, contest, teacher)['rows'][0]['solved'] == 1


def test_rejudge_preserves_the_verdict_visible_before_freeze(arena):
    db, teacher, student, problem, contest = arena
    item = submission(db, student, problem, contest, 'ACCEPTED', 2)
    contest.freeze_at = contest.start_time + 4*60
    item.history = [{'status': 'ACCEPTED', 'finished_at': item.finished_at}]
    item.status = 'WRONG_ANSWER'
    item.finished_at = contest.start_time + 5*60
    db.commit()
    assert scoreboard(db, contest, student)['rows'][0]['solved'] == 1
    assert scoreboard(db, contest, teacher)['rows'][0]['solved'] == 0
