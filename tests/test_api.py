"""Authorization and queue admission tests; no real accounts or persistent DB."""
import io
import sys
import time
import zipfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'backend'))
from app.db import Base, get_db
from app.main import app
from app.models import User, Problem, TestCase as ProblemTest, Contest, ContestProblem, ContestParticipant, SystemSetting, Submission, SubmissionTestResult
from app.security import hash_password

PREFIX = '/api/v1'
PASSWORD = 'Temporary-test-password-483'


@pytest.fixture
def arena(tmp_path, monkeypatch):
    from app.middleware.limits import limiter
    limiter.reset()
    engine = create_engine(f'sqlite:///{(tmp_path / "api.db").as_posix()}', connect_args={'check_same_thread': False, 'timeout': 10})
    Base.metadata.create_all(engine)
    sessions = sessionmaker(engine, expire_on_commit=False)
    def database():
        with sessions() as db:
            yield db
    app.dependency_overrides[get_db] = database
    monkeypatch.setattr('app.main.SessionLocal', sessions)
    monkeypatch.setattr('app.security.SessionLocal', sessions)
    monkeypatch.setenv('SUBMIT_COOLDOWN_SECONDS', '5')
    monkeypatch.setenv('RUN_COOLDOWN_SECONDS', '2')
    with TestClient(app) as admin:
        response = admin.post(PREFIX+'/auth/setup', json={'username':'admin','password':PASSWORD,'name':'Administrator','organization':'Test University'})
        assert response.status_code == 201, response.text
        admin.headers['X-CSRF-Token'] = admin.cookies['ca_csrf']
        hashed = hash_password(PASSWORD)
        with sessions() as db:
            teacher = User(username='teacher', name='Teacher', role='TEACHER', password_hash=hashed)
            outsider = User(username='outsider', name='Other Teacher', role='TEACHER', password_hash=hashed)
            db.add_all([teacher, outsider]); db.flush()
            student = User(username='student', name='Student', role='STUDENT', password_hash=hashed, creator_id=teacher.id)
            other = User(username='otherstudent', name='Other Student', role='STUDENT', password_hash=hashed, creator_id=teacher.id)
            db.add_all([student, other]); db.flush()
            problem = Problem(title='Secret sum', slug='sum', description='Read two integers and sum them.', difficulty='EASY', author_id=teacher.id)
            unrelated = Problem(title='Unassigned', slug='other', description='Unassigned problem', difficulty='EASY', author_id=teacher.id)
            contest = Contest(title='Test contest', author_id=teacher.id, start_time=time.time()-60, end_time=time.time()+3600)
            db.add_all([problem, unrelated, contest]); db.flush()
            db.add_all([ProblemTest(problem_id=problem.id, ordinal=0, input_data='1 2', expected='3', is_sample=True),
                        ProblemTest(problem_id=problem.id, ordinal=1, input_data='HIDDEN_INPUT_8372', expected='HIDDEN_OUTPUT_5291', is_sample=False),
                        ContestProblem(contest_id=contest.id, problem_id=problem.id, ordinal=0),
                        ContestParticipant(contest_id=contest.id, user_id=student.id),
                        ContestParticipant(contest_id=contest.id, user_id=other.id),
                        SystemSetting(key='judge_heartbeat', value={'available': True, 'time': time.time()})])
            db.commit()
            ids = {'contest': contest.id, 'problem': problem.id, 'unrelated': unrelated.id, 'student': student.id}
        clients = {'admin': admin}
        for index, username in enumerate(('teacher','outsider','student','otherstudent'), 1):
            client = TestClient(app, client=(f'192.0.2.{index}', 50000))
            result = client.post(PREFIX+'/auth/login',json={'username':username,'password':PASSWORD})
            assert result.status_code == 200, result.text
            client.headers['X-CSRF-Token'] = client.cookies['ca_csrf']
            clients[username] = client
        yield clients, sessions, ids
        for name, client in clients.items():
            if name != 'admin': client.close()
    app.dependency_overrides.clear()
    engine.dispose()


def payload(ids, **kwargs):
    return {'contest_id':ids['contest'], 'problem_id':ids['problem'], 'source':'print(sum(map(int,input().split())))', **kwargs}


def test_setup_locked_session_cookie_and_csrf(arena):
    clients, _, _ = arena
    admin = clients['admin']
    assert admin.get(PREFIX+'/auth/status').json()['setup_required'] is False
    assert admin.post(PREFIX+'/auth/setup',json={'username':'hacker','password':PASSWORD,'name':'Hacker','organization':'Other'}).status_code == 409
    session_cookie = next(c for c in admin.cookies.jar if c.name == 'ca_session')
    assert 'HttpOnly' in session_cookie._rest
    assert session_cookie._rest['SameSite'] == 'strict'
    assert admin.post(PREFIX+'/groups',json={'name':'No CSRF'},headers={'X-CSRF-Token':''}).status_code == 403
    assert admin.post(PREFIX+'/groups',json={'name':'Bad origin'},headers={'Origin':'https://evil.invalid'}).status_code == 403
    assert clients['student'].post(PREFIX+'/users',json={'username':'escalate','name':'Escalate','password':PASSWORD,'role':'TEACHER'}).status_code == 403


def test_hidden_tests_and_future_problem_content_are_inaccessible(arena):
    clients, sessions, ids = arena
    student = clients['student']
    path = f"{PREFIX}/problems/{ids['problem']}?contest_id={ids['contest']}"
    result = student.get(path)
    assert result.status_code == 200
    assert len(result.json()['tests']) == 1
    assert 'HIDDEN_' not in result.text
    assert student.get(PREFIX+'/problems').status_code == 403
    assert student.get(f"{PREFIX}/problems/{ids['problem']}/export").status_code == 403
    assert student.get(f"{PREFIX}/problems/{ids['unrelated']}?contest_id={ids['contest']}").status_code == 403
    with sessions() as db:
        contest = db.get(Contest, ids['contest']); contest.start_time = time.time()+600; contest.end_time = time.time()+3600; db.commit()
    assert student.get(path).status_code == 403
    assert student.get(f"{PREFIX}/contests/{ids['contest']}").json()['problems'] == []
    assert student.post(PREFIX+'/submissions',json=payload(ids)).status_code == 403


@pytest.mark.parametrize('state', ['PAUSED','FINISHED','ARCHIVED'])
def test_non_running_contest_rejects_submit(arena, state):
    clients, sessions, ids = arena
    with sessions() as db:
        db.get(Contest,ids['contest']).status = state; db.commit()
    assert clients['student'].post(PREFIX+'/submissions',json=payload(ids)).status_code in (403,404)


def test_idor_hidden_result_output_and_fail_closed_judge(arena):
    clients, sessions, ids = arena
    result = clients['student'].post(PREFIX+'/submissions',json=payload(ids))
    assert result.status_code == 202, result.text
    sid = result.json()['id']
    with sessions() as db:
        item = db.get(Submission,sid); item.status = 'WRONG_ANSWER'; item.error = 'HIDDEN_OUTPUT_5291'
        db.add(SubmissionTestResult(submission_id=sid,ordinal=1,verdict='WRONG_ANSWER',stdout='HIDDEN_OUTPUT_5291',stderr='HIDDEN_INPUT_8372',is_sample=False))
        db.commit()
    own = clients['student'].get(f'{PREFIX}/submissions/{sid}')
    assert own.status_code == 200
    assert 'HIDDEN_' not in own.text
    assert own.json()['tests'] == []
    assert clients['otherstudent'].get(f'{PREFIX}/submissions/{sid}').status_code == 404
    assert clients['outsider'].get(f'{PREFIX}/submissions/{sid}').status_code == 404
    assert clients['outsider'].post(f'{PREFIX}/submissions/{sid}/rejudge').status_code == 404
    with sessions() as db:
        db.get(SystemSetting,'judge_heartbeat').value = {'available':False,'time':time.time()}; db.commit()
    assert clients['otherstudent'].post(PREFIX+'/submissions',json=payload(ids)).status_code == 503


def test_concurrent_submit_serializes_rate_limit_and_distinguishes_run(arena):
    clients, sessions, ids = arena
    student = clients['student']
    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(pool.map(lambda _: student.post(PREFIX+'/submissions',json=payload(ids)), range(2)))
    assert sorted(r.status_code for r in responses) == [202,429], [r.text for r in responses]
    run = student.post(PREFIX+'/submissions',json=payload(ids,kind='RUN'))
    assert run.status_code == 202, run.text
    with sessions() as db:
        official = db.scalar(select(Submission).where(Submission.kind=='SUBMIT'))
        trial = db.scalar(select(Submission).where(Submission.kind=='RUN'))
        assert len(official.problem_snapshot['tests']) == 2
        assert len(trial.problem_snapshot['tests']) == 1


def test_teacher_ownership_and_zip_path_traversal(arena):
    clients, _, ids = arena
    assert clients['outsider'].get(f"{PREFIX}/problems/{ids['problem']}/export").status_code == 404
    assert clients['outsider'].post(f"{PREFIX}/contests/{ids['contest']}/pause").status_code == 404
    blob = io.BytesIO()
    with zipfile.ZipFile(blob,'w') as archive:
        archive.writestr('../escape.txt','do not extract')
        archive.writestr('problem.json','{}')
    response = clients['teacher'].post(PREFIX+'/problems/import',files={'file':('unsafe.zip',blob.getvalue(),'application/zip')})
    assert response.status_code == 400, response.text


def test_password_change_revokes_existing_sessions(arena):
    clients, _, _ = arena
    student = clients['student']
    with TestClient(app) as second:
        assert second.post(PREFIX+'/auth/login',json={'username':'student','password':PASSWORD}).status_code == 200
        result = student.post(PREFIX+'/auth/password',json={'old_password':PASSWORD,'new_password':'Replacement-password-7264'})
        assert result.status_code == 200, result.text
        assert second.get(PREFIX+'/auth/me').status_code == 401
        assert second.post(PREFIX+'/auth/login',json={'username':'student','password':PASSWORD}).status_code == 401
        assert second.post(PREFIX+'/auth/login',json={'username':'student','password':'Replacement-password-7264'}).status_code == 200


def test_zip_roundtrip_preserves_tests_and_tag_search(arena):
    clients, _, _ = arena
    teacher = clients['teacher']
    problem = {'title':'Roundtrip problem','description':'Add two whole numbers.', 'tags':['math','intro'],
               'tests':[{'input_data':'1 2','expected':'3','is_sample':True}, {'input_data':'99 10','expected':'109','is_sample':False}]}
    created = teacher.post(PREFIX+'/problems',json=problem)
    assert created.status_code == 201, created.text
    export = teacher.get(f"{PREFIX}/problems/{created.json()['id']}/export")
    assert export.status_code == 200
    imported = teacher.post(PREFIX+'/problems/import',files={'file':('problem.zip',export.content,'application/zip')})
    assert imported.status_code == 201, imported.text
    assert imported.json()['tests'] == [{**t, 'weight': 1} for t in problem['tests']]
    assert imported.json()['tags'] == problem['tags']
    assert len(teacher.get(PREFIX+'/problems?tag=math&q=Roundtrip').json()) == 2
    assert teacher.get(PREFIX+'/problems?tag=absent').json() == []


def test_websocket_origin_membership_and_payload_privacy(arena):
    clients, _, ids = arena
    path = f"/ws/contests/{ids['contest']}"
    for client, origin in [(clients['student'],'https://evil.invalid'), (clients['outsider'],'http://testserver')]:
        with pytest.raises(WebSocketDisconnect):
            with client.websocket_connect(path,headers={'Origin':origin}):
                pass
    with TestClient(app) as anonymous:
        with pytest.raises(WebSocketDisconnect):
            with anonymous.websocket_connect(path,headers={'Origin':'http://testserver'}):
                pass
    result = clients['student'].post(PREFIX+'/submissions',json=payload(ids))
    assert result.status_code == 202
    with clients['student'].websocket_connect(path,headers={'Origin':'http://testserver'}) as ws:
        data = ws.receive_json()
        assert data['submissions'] == [{'id':result.json()['id'],'status':'QUEUED'}]
        assert 'source' not in str(data) and 'HIDDEN_' not in str(data)
    with clients['otherstudent'].websocket_connect(path,headers={'Origin':'http://testserver'}) as ws:
        assert ws.receive_json()['submissions'] == []


def test_authoring_and_contest_lifecycle(arena):
    clients, _, ids = arena
    teacher = clients['teacher']
    group = teacher.post(PREFIX+'/groups',json={'name':'New group'})
    assert group.status_code == 201
    gid = group.json()['id']
    bulk = teacher.post(f'{PREFIX}/groups/{gid}/students',json={'prefix':'batch','count':2})
    assert bulk.status_code == 201, bulk.text
    assert len(bulk.json()['credentials']) == 2
    listing = teacher.get(PREFIX+'/groups').json()
    assert next(g for g in listing if g['id']==gid)['member_count'] == 2
    assert 'password' not in str(listing)
    cid = ids['contest']
    for action, expected in [('pause','PAUSED'),('resume','RUNNING')]:
        result = teacher.post(f'{PREFIX}/contests/{cid}/{action}')
        assert result.status_code == 200, result.text
        assert result.json()['status'] == expected
    question = clients['student'].post(f'{PREFIX}/contests/{cid}/clarifications',json={'question':'Is integer input guaranteed?','problem_id':ids['problem']})
    assert question.status_code == 201, question.text
    assert clients['otherstudent'].get(f'{PREFIX}/contests/{cid}/clarifications').json() == []
    answer = teacher.patch(f"{PREFIX}/clarifications/{question.json()['id']}",json={'answer':'Yes, integers only.','is_public':True})
    assert answer.status_code == 200
    assert clients['otherstudent'].get(f'{PREFIX}/contests/{cid}/clarifications').json()[0]['answer'] == 'Yes, integers only.'
    announce = teacher.post(f'{PREFIX}/contests/{cid}/announcements',json={'message':'Ten minutes left'})
    assert announce.status_code == 201, announce.text
    assert clients['student'].get(f'{PREFIX}/contests/{cid}/announcements').json()[0]['message'] == 'Ten minutes left'
    assert teacher.get(f'{PREFIX}/contests/{cid}/scoreboard.csv').status_code == 200
    assert teacher.post(f'{PREFIX}/contests/{cid}/finish').json()['status'] == 'FINISHED'


def test_execution_policy_pause_resume_and_offline_worker(arena):
    clients, sessions, ids = arena
    path = f"{PREFIX}/contests/{ids['contest']}"
    student = clients['student']
    assert student.get(path).json()['execution'] == {'allowed': True, 'reason': None}
    assert clients['teacher'].post(path+'/pause').status_code == 200
    detail = student.get(path).json()
    assert detail['execution'] == {'allowed': False, 'reason': 'CONTEST_PAUSED'}
    assert detail['can_manage'] is False
    assert clients['teacher'].get(path).json()['can_manage'] is True
    for kind in ('RUN', 'SUBMIT'):
        response = student.post(PREFIX+'/submissions', json=payload(ids, kind=kind))
        assert response.status_code == 403
        assert response.json()['detail'] == 'CONTEST_PAUSED'
    assert student.post(path+'/resume').status_code == 403
    assert clients['teacher'].post(path+'/resume').status_code == 200
    assert student.get(path).json()['execution']['allowed'] is True
    assert student.post(PREFIX+'/submissions', json=payload(ids, kind='RUN')).status_code == 202
    with sessions() as db:
        db.get(SystemSetting, 'judge_heartbeat').value = {'available': True, 'time': time.time()-60}
        db.commit()
    assert student.get(path).json()['execution']['reason'] == 'JUDGE_UNAVAILABLE'
    assert student.post(PREFIX+'/submissions', json=payload(ids)).status_code == 503


def test_concurrent_idempotent_retry_and_conflict(arena):
    from uuid import uuid4
    clients, sessions, ids = arena
    student = clients['student']
    body = payload(ids, request_id=str(uuid4()))
    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(pool.map(lambda _: student.post(PREFIX+'/submissions', json=body), range(2)))
    assert [r.status_code for r in responses] == [202, 202], [r.text for r in responses]
    assert responses[0].json()['id'] == responses[1].json()['id']
    with sessions() as db:
        assert len(db.scalars(select(Submission)).all()) == 1
        db.get(Contest, ids['contest']).status = 'FINISHED'
        db.commit()
    # Recover a successful request whose HTTP response was lost, even after finish.
    retry = student.post(PREFIX+'/submissions', json=body)
    assert retry.status_code == 202
    assert retry.json()['id'] == responses[0].json()['id']
    conflict = student.post(PREFIX+'/submissions', json={**body, 'source':'print(123)'})
    assert conflict.status_code == 409
    assert conflict.json()['detail'] == 'IDEMPOTENCY_CONFLICT'


def test_student_password_reset_revokes_sessions_and_checks_owner(arena):
    from app.models import AuditLog
    clients, sessions, ids = arena
    path = f"{PREFIX}/users/{ids['student']}/reset-password"
    body = {'new_password': 'New-student-password-123'}
    assert clients['outsider'].post(path, json=body).status_code == 404
    assert clients['student'].post(path, json=body).status_code == 403
    assert clients['teacher'].post(path, json={'new_password':'short'}).status_code == 422
    assert clients['teacher'].post(path, json=body, headers={'X-CSRF-Token':''}).status_code == 403
    assert clients['teacher'].post(path, json=body).status_code == 204
    assert clients['student'].get(PREFIX+'/auth/me').status_code == 401
    assert clients['student'].post(PREFIX+'/auth/login', json={'username':'student','password':PASSWORD}).status_code == 401
    assert clients['student'].post(PREFIX+'/auth/login', json={'username':'student','password':body['new_password']}).status_code == 200
    with sessions() as db:
        assert body['new_password'] not in str([row.detail for row in db.scalars(select(AuditLog))])
    # Even administrators cannot reset another administrator through this endpoint.
    admin_id = clients['admin'].get(PREFIX+'/auth/me').json()['id']
    assert clients['admin'].post(f'{PREFIX}/users/{admin_id}/reset-password', json=body).status_code == 404


def test_delete_group_preserves_accounts_and_removes_contest_link(arena):
    from app.models import Group, GroupMember, ContestGroup
    clients, sessions, ids = arena
    group = clients['teacher'].post(PREFIX+'/groups', json={'name':'Class A'}).json()
    path = f"{PREFIX}/groups/{group['id']}"
    assert clients['teacher'].post(path+'/members', json={'user_ids':[ids['student']]}).status_code == 200
    with sessions() as db:
        db.add(ContestGroup(group_id=group['id'], contest_id=ids['contest'])); db.commit()
    assert clients['outsider'].delete(path).status_code == 404
    assert clients['student'].delete(path).status_code == 403
    assert clients['teacher'].delete(path).status_code == 204
    with sessions() as db:
        assert db.get(Group,group['id']) is None
        assert db.get(User,ids['student']).active
        assert db.get(GroupMember,(group['id'],ids['student'])) is None
        assert db.get(ContestGroup,(ids['contest'],group['id'])) is None
    assert clients['student'].get(PREFIX+'/auth/me').status_code == 200


def test_delete_student_revokes_access_retains_submissions(arena):
    from app.models import GroupMember
    clients, sessions, ids = arena
    sid = clients['student'].post(PREFIX+'/submissions',json=payload(ids)).json()['id']
    path = f"{PREFIX}/users/{ids['student']}"
    assert clients['outsider'].delete(path).status_code == 404
    assert clients['student'].delete(path).status_code == 403
    assert clients['admin'].delete(path).status_code == 204
    assert clients['student'].get(PREFIX+'/auth/me').status_code == 401
    assert clients['student'].post(PREFIX+'/auth/login',json={'username':'student','password':PASSWORD}).status_code == 401
    assert ids['student'] not in [u['id'] for u in clients['teacher'].get(PREFIX+'/users').json()]
    assert clients['teacher'].post(path+'/reset-password',json={'new_password':'New-password-123'}).status_code == 404
    with sessions() as db:
        assert not db.get(User,ids['student']).active
        assert db.get(Submission,sid) is not None
        assert not db.scalars(select(GroupMember).where(GroupMember.user_id==ids['student'])).all()
        assert db.get(ContestParticipant,(ids['contest'],ids['student'])) is None


def test_reset_cannot_race_login_with_previous_password(arena, monkeypatch):
    import threading
    import app.routes.auth as auth
    clients, _, ids = arena
    checking = threading.Event()
    release = threading.Event()
    resetting = threading.Event()
    original = auth.verify_password
    def slow_verify(password, hashed):
        checking.set()
        assert release.wait(5)
        return original(password, hashed)
    monkeypatch.setattr(auth, 'verify_password', slow_verify)
    login_client = TestClient(app)
    def reset():
        resetting.set()
        return clients['teacher'].post(f"{PREFIX}/users/{ids['student']}/reset-password",json={'new_password':'Replacement-password-123'})
    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            login = pool.submit(login_client.post, PREFIX+'/auth/login',json={'username':'student','password':PASSWORD})
            assert checking.wait(5)
            changed = pool.submit(reset)
            assert resetting.wait(5)
            try:
                from concurrent.futures import TimeoutError
                with pytest.raises(TimeoutError):
                    changed.result(timeout=0.2)
            finally:
                release.set()
            assert login.result().status_code == 200
            assert changed.result().status_code == 204
        assert login_client.get(PREFIX+'/auth/me').status_code == 401
    finally:
        release.set()
        login_client.close()
