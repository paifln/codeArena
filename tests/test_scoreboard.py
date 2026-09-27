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


def test_compile_errors_never_penalize_and_unsolved_time_is_zero(arena):
    db,teacher,student,problem,contest=arena
    submission(db,student,problem,contest,'COMPILATION_ERROR',1)
    submission(db,student,problem,contest,'WRONG_ANSWER',2)
    assert scoreboard(db,contest,student)['rows'][0]['penalty']==0
    submission(db,student,problem,contest,'ACCEPTED',35)
    row=scoreboard(db,contest,student)['rows'][0]
    assert row['penalty']==55 and row['cells'][0]['attempts']==1
    assert row['cells'][0]['time_minutes']==35 and row['cells'][0]['penalty_minutes']==20


def test_equal_results_share_rank_and_training_has_no_penalty(arena):
    db,teacher,student,problem,contest=arena
    other=User(username='second',name='A Student',role='STUDENT',password_hash='unused')
    db.add(other);db.flush();db.add(ContestParticipant(contest_id=contest.id,user_id=other.id));db.commit()
    submission(db,student,problem,contest,'ACCEPTED',5)
    submission(db,other,problem,contest,'ACCEPTED',5)
    rows=scoreboard(db,contest,student)['rows']
    assert [r['rank'] for r in rows]==[1,1] and rows[0]['name']=='A Student'
    contest.scoring='EDUCATIONAL';db.commit()
    assert all(r['penalty']==0 for r in scoreboard(db,contest,student)['rows'])


def test_partial_uses_best_submission_not_sum(arena):
    db,teacher,student,problem,contest=arena
    contest.scoring='PARTIAL';db.commit()
    submission(db,student,problem,contest,'PARTIAL',1,score=30)
    submission(db,student,problem,contest,'PARTIAL',2,score=60)
    submission(db,student,problem,contest,'PARTIAL',3,score=20)
    row=scoreboard(db,contest,student)['rows'][0]
    assert row['score']==60 and row['penalty']==0 and row['solved']==0


def test_last_acceptance_breaks_equal_icpc_totals(arena):
    db,teacher,student,problem,contest=arena
    other=User(username='other',name='Other',role='STUDENT',password_hash='unused')
    db.add(other);db.flush();db.add(ContestParticipant(contest_id=contest.id,user_id=other.id));db.commit()
    submission(db,student,problem,contest,'ACCEPTED',25)
    submission(db,other,problem,contest,'WRONG_ANSWER',1)
    submission(db,other,problem,contest,'ACCEPTED',5)
    rows=scoreboard(db,contest,student)['rows']
    assert rows[0]['user_id']==other.id and rows[0]['penalty']==rows[1]['penalty']==25
    assert [row['rank'] for row in rows]==[1,2]
