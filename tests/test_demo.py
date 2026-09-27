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


def test_demo_replacement_preserves_students_and_other_contests(tmp_path):
    from sqlalchemy import event
    from app.models import Group, GroupMember, ContestGroup
    from app.replace_demo import replace_demo
    engine = create_engine(f"sqlite:///{tmp_path / 'replace.db'}")
    @event.listens_for(engine, 'connect')
    def foreign_keys(connection, _):
        connection.execute('PRAGMA foreign_keys=ON')
    Base.metadata.create_all(engine)
    factory = sessionmaker(engine)
    with factory() as db:
        db.add(User(username='owner', name='Owner', password_hash='unchanged', role='ADMIN'))
        db.commit()
    with factory() as db:
        old_id, _ = create_demo(db, 1)
    with factory() as db:
        gid = db.scalar(select(ContestGroup.group_id).where(ContestGroup.contest_id==old_id))
        student = User(username='student', name='Student', password_hash='keep-this', role='STUDENT',creator_id=1)
        db.add(student);db.flush()
        uid = student.id
        db.add(GroupMember(group_id=gid,user_id=uid))
        other = Contest(title='Real assessment',author_id=1,start_time=1,end_time=100,status='FINISHED')
        db.add(other);db.commit();other_id=other.id
    with factory() as db:
        new_id, new_gid = replace_demo(db,1,[gid],start=True)
    with factory() as db:
        assert new_id != old_id and new_gid != gid
        assert db.get(Contest,old_id) is None and db.get(Group,gid) is None
        assert db.get(Contest,other_id).title == 'Real assessment'
        assert db.get(User,uid).password_hash == 'keep-this'
        assert db.get(GroupMember,(new_gid,uid)) is not None
        assert db.get(Contest,new_id).status == 'RUNNING'
        assert db.scalar(select(func.count()).select_from(ProblemTest)) == 15
    engine.dispose()
