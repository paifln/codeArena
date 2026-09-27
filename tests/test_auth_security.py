import time
import jwt
from sqlalchemy import select
from test_api import arena, PREFIX, PASSWORD, payload
from app.config import settings
from app.models import RefreshToken, User, RateLimit
from app.security import decode_token, verify_password


def test_rotation_replay_revokes_session_and_jwt_lifetimes(arena):
    clients, factory, _ = arena
    client = clients['student']
    access = decode_token(client.cookies['ca_session'], 'access')
    original = client.cookies['ca_refresh']
    refresh = decode_token(original, 'refresh')
    assert access['exp'] - access['iat'] == 900
    assert refresh['exp'] - refresh['iat'] == 604800
    assert client.post(PREFIX+'/auth/refresh').status_code == 200
    assert client.cookies['ca_refresh'] != original
    with factory() as db:
        assert db.get(RefreshToken, refresh['jti']).revoked
    response = client.post(PREFIX+'/auth/refresh', headers={
        'Cookie': 'ca_refresh='+original,
        'X-CSRF-Token': client.cookies['ca_csrf']})
    assert response.status_code == 401
    assert client.get(PREFIX+'/auth/me').status_code == 401


def test_expired_access_refresh_csrf_reset_and_cookie_flags(arena):
    clients, factory, ids = arena
    client = clients['student']
    claims = decode_token(client.cookies['ca_session'], 'access')
    claims['exp'] = int(time.time())-1
    expired = jwt.encode(claims, settings().secret_key.get_secret_value(), algorithm='HS256')
    assert client.get(PREFIX+'/auth/me', headers={'Cookie':'ca_session='+expired}).status_code == 401
    assert client.post(PREFIX+'/auth/refresh', headers={'X-CSRF-Token':''}).status_code == 403
    response = client.post(PREFIX+'/auth/refresh')
    assert response.status_code == 200
    for cookie in ('ca_session','ca_refresh'):
        assert any(cookie+'=' in h and 'HttpOnly' in h and 'SameSite=strict' in h for h in response.headers.get_list('set-cookie'))
    assert clients['teacher'].post(f"{PREFIX}/users/{ids['student']}/reset-password", json={'new_password':'New-password-9876'}).status_code == 204
    assert client.post(PREFIX+'/auth/refresh').status_code == 401
    with factory() as db:
        assert all(t.revoked for t in db.scalars(select(RefreshToken).where(RefreshToken.user_id==ids['student'])))
        hashed = db.get(User, ids['student']).password_hash
        assert hashed.startswith('$2b$12$') and verify_password('New-password-9876', hashed)


def test_strict_payload_utf8_code_limit_and_error_headers(arena):
    clients, _, ids = arena
    client=clients['student']
    assert client.post(PREFIX+'/submissions', json=payload(ids, contest_id=str(ids['contest']))).status_code == 422
    assert client.post(PREFIX+'/submissions', json=payload(ids, source='я'*32769)).status_code == 422
    assert client.post(PREFIX+'/submissions', json=payload(ids, practice='false')).status_code == 422
    response=client.post(PREFIX+'/submissions', content=b'x'*(10*1024*1024+1))
    assert response.status_code == 413
    for header in ('Content-Security-Policy','Strict-Transport-Security','Permissions-Policy','X-Frame-Options'):
        assert header in response.headers


def test_login_window_persists_failed_attempts(arena):
    clients, factory, _ = arena
    # The fixture used one attempt from the student's own address.
    client=clients['student']
    for _ in range(4):
        assert client.post(PREFIX+'/auth/login',json={'username':'student','password':'wrong'}).status_code == 401
    from app.middleware.limits import limiter
    limiter.reset()  # Model a process restart: SQLite's 15-minute limit remains.
    assert client.post(PREFIX+'/auth/login',json={'username':'student','password':PASSWORD}).status_code == 429
    with factory() as db:
        row=db.get(RateLimit,'login:192.0.2.3')
        assert row.count == 5 and row.reset_at-time.time() > 800


def test_default_account_limit_cannot_be_bypassed_by_changing_routes(arena):
    clients, _, _ = arena
    from app.middleware.limits import limiter
    limiter.reset()
    client=clients['student']
    for index in range(100):
        path='/auth/me' if index%2 else '/auth/status'
        assert client.get(PREFIX+path).status_code == 200
    assert client.get(PREFIX+'/contests').status_code == 429


def test_backup_download_is_admin_only_and_filename_is_bounded(arena, tmp_path, monkeypatch):
    clients, _, _ = arena
    monkeypatch.setenv('BACKUP_DIR', str(tmp_path))
    (tmp_path/'codearena-123.db').write_bytes(b'backup fixture')
    (tmp_path/'private.txt').write_text('not a backup')
    path=PREFIX+'/operations/backups/codearena-123.db'
    assert clients['student'].get(path).status_code == 403
    assert clients['teacher'].get(path).status_code == 403
    assert clients['admin'].get(path).content == b'backup fixture'
    assert clients['admin'].get(PREFIX+'/operations/backups/private.txt').status_code == 404
    assert clients['admin'].get(PREFIX+'/operations/backups/..%5Cprivate.txt').status_code == 404
    assert [x['file'] for x in clients['admin'].get(PREFIX+'/operations/backups').json()] == ['codearena-123.db']


def test_token_type_signature_and_legacy_hash_upgrade(arena):
    clients, factory, ids = arena
    client=clients['student']
    assert client.get(PREFIX+'/auth/me', headers={'Cookie':'ca_session='+client.cookies['ca_refresh']}).status_code == 401
    raw=client.cookies['ca_session']
    head,body,_=raw.split('.')
    assert client.get(PREFIX+'/auth/me', headers={'Cookie':f'ca_session={head}.{body}.AAAA'}).status_code == 401
    from app.security import hasher
    with factory() as db:
        db.get(User,ids['student']).password_hash=hasher.hash(PASSWORD)
        db.commit()
    assert client.post(PREFIX+'/auth/login',json={'username':'student','password':PASSWORD}).status_code == 200
    with factory() as db:
        assert db.get(User,ids['student']).password_hash.startswith('$2b$12$')


def test_secret_configuration_fails_closed(monkeypatch):
    import pytest
    from pydantic import ValidationError
    from app.config import Settings
    monkeypatch.delenv('SECRET_KEY')
    with pytest.raises(ValidationError):
        Settings(_env_file=None)
    with pytest.raises(ValidationError):
        Settings(secret_key='short', _env_file=None)


def test_logs_exclude_exception_text_and_request_content():
    import logging
    from app.middleware.logging import JsonFormatter
    record=logging.LogRecord('uvicorn.error', logging.ERROR, '', 0, 'secret-password', (), None)
    assert 'secret-password' not in JsonFormatter().format(record)
