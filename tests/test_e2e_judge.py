"""Real API -> durable database -> Docker worker -> standings, on an ephemeral DB."""
import os
from datetime import datetime, timedelta, timezone
import pytest

pytestmark = pytest.mark.skipif(os.environ.get('RUN_SANDBOX_TESTS') != '1', reason='requires built Docker sandbox')


def test_complete_contest_with_real_docker(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient
    from sqlalchemy import create_engine, event
    from sqlalchemy.orm import sessionmaker
    from app.db import Base, get_db
    from app.main import app
    from judge.sandbox import DockerSandbox
    from judge.worker import heartbeat, run_once

    sandbox = DockerSandbox()
    available, detail = sandbox.available()
    assert available, detail
    monkeypatch.setenv('SUBMIT_COOLDOWN_SECONDS', '0')
    engine = create_engine(f'sqlite:///{tmp_path / "e2e.db"}', connect_args={'check_same_thread': False})
    @event.listens_for(engine, 'connect')
    def settings(connection, _):
        connection.execute('PRAGMA foreign_keys=ON')
        connection.execute('PRAGMA journal_mode=WAL')
    Base.metadata.create_all(engine)
    factory = sessionmaker(engine, expire_on_commit=False)
    monkeypatch.setattr('app.security.SessionLocal', factory)
    def database():
        with factory() as db:
            yield db
    previous = app.dependency_overrides.copy()
    app.dependency_overrides[get_db] = database
    prefix = '/api/v1'
    def post(client, path, body=None, expected=201):
        response = client.post(prefix + path, json=body,
                               headers={'X-CSRF-Token': client.cookies.get('ca_csrf', '')})
        assert response.status_code == expected, response.text
        return response.json()
    try:
        with TestClient(app) as admin, TestClient(app) as teacher, TestClient(app) as student:
            password = 'e2e-test-only-password'
            post(admin, '/auth/setup', {'username':'administrator','password':password,
                 'name':'Administrator','organization':'Ephemeral integration school'})
            post(admin, '/users', {'username':'teacher','password':password,'name':'Teacher','role':'TEACHER'})
            post(teacher, '/auth/login', {'username':'teacher','password':password}, 200)
            pupil = post(teacher, '/users', {'username':'student','password':password,'name':'Student','role':'STUDENT'})
            group = post(teacher, '/groups', {'name':'Integration class'})
            post(teacher, f'/groups/{group["id"]}/members', {'user_ids':[pupil['id']]}, 200)
            problem = post(teacher, '/problems', {'title':'Sum two integers','description':'Read two integers and print their sum.',
                'tests':[{'input_data':'1 2','expected':'3','is_sample':True},
                         {'input_data':'981234 56789','expected':'1038023','is_sample':False}]})
            now = datetime.now(timezone.utc)
            contest = post(teacher, '/contests', {'title':'Integration contest',
                'start_time':(now+timedelta(hours=1)).isoformat(),'end_time':(now+timedelta(hours=2)).isoformat(),
                'problem_ids':[problem['id']],'group_ids':[group['id']]})
            post(teacher, f'/contests/{contest["id"]}/start', expected=200)
            post(student, '/auth/login', {'username':'student','password':password}, 200)
            heartbeat(factory, True, 'Live integration sandbox')
            base = {'contest_id':contest['id'],'problem_id':problem['id'],'language':'python3'}

            def submit(source, kind, verdict):
                queued = post(student, '/submissions', {**base,'source':source,'kind':kind}, 202)
                assert queued['status'] == 'QUEUED'
                assert run_once(factory, sandbox)
                result = student.get(prefix+f'/submissions/{queued["id"]}').json()
                assert result['status'] == verdict, result
                return result

            sample = submit('print(sum(map(int,input().split())))', 'RUN', 'ACCEPTED')
            assert len(sample['tests']) == 1 and sample['tests'][0]['stdout'] == '3\n'
            wrong = submit('print(3)', 'SUBMIT', 'WRONG_ANSWER')
            assert wrong['tests'] == []
            hidden = teacher.get(prefix+f'/submissions/{wrong["id"]}').json()
            assert len(hidden['tests']) == 2
            # Echoing the hidden input may not leak it through submission diagnostics.
            echo = submit('s=input();print(3 if s=="1 2" else s)', 'SUBMIT', 'WRONG_ANSWER')
            assert echo['tests'] == [] and '981234' not in str({k:v for k,v in echo.items() if k!='source'})
            accepted = submit('if __name__ == "__main__":\n print(sum(map(int,input().split())))', 'SUBMIT', 'ACCEPTED')
            assert accepted['tests'] == []
            board = student.get(prefix+f'/contests/{contest["id"]}/scoreboard').json()
            row = board['rows'][0]
            assert row['solved'] == 1 and row['penalty'] == 40
            assert row['cells'][0]['attempts'] == 2
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(previous)
        engine.dispose()
