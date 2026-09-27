import secrets
import time
import bcrypt
import jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerificationError, InvalidHashError
from fastapi import Depends, HTTPException, Request, Response
from .db import SessionLocal
from .models import User, Session, RateLimit, RefreshToken
from .config import settings

hasher = PasswordHasher(time_cost=2, memory_cost=19456, parallelism=1)
DUMMY_HASH = bcrypt.hashpw(secrets.token_bytes(32), bcrypt.gensalt(rounds=12)).decode()


def hash_password(password):
    if len(password.encode()) > 72:
        raise HTTPException(422, "Password must not exceed 72 UTF-8 bytes")
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt(rounds=12)).decode()


def verify_password(password, hashed):
    try:
        if hashed.startswith("$2"):
            return bcrypt.checkpw(password.encode(), hashed.encode())
        return hasher.verify(hashed, password)
    except (VerificationError, InvalidHashError, ValueError):
        return False


def session_id(raw):
    try:
        return decode_token(raw, "access")["sid"]
    except HTTPException:
        return ""


def decode_token(raw, kind):
    try:
        claims = jwt.decode(raw, settings().secret_key.get_secret_value(),
            algorithms=["HS256"], issuer="codearena", audience="codearena",
            options={"require": ["exp", "iat", "sub", "jti", "sid", "type"]})
        if claims["type"] != kind or not isinstance(claims["sid"], str):
            raise jwt.InvalidTokenError()
        return claims
    except jwt.InvalidTokenError:
        raise HTTPException(401, "Authentication required") from None


def issue_tokens(db, response, session):
    now = int(time.time())
    for kind, cookie, lifetime in (("access", "ca_session", 900), ("refresh", "ca_refresh", 604800)):
        expires = min(now + lifetime, int(session.expires_at))
        jti = secrets.token_hex(32)
        token = jwt.encode({"sub": str(session.user_id), "sid": session.id,
            "jti": jti, "iat": now, "exp": expires, "type": kind,
            "iss": "codearena", "aud": "codearena"},
            settings().secret_key.get_secret_value(), algorithm="HS256")
        if kind == "refresh":
            db.add(RefreshToken(id=jti, session_id=session.id, user_id=session.user_id,
                expires_at=expires, revoked=False))
        response.set_cookie(cookie, token, max_age=expires-now, httponly=True,
            secure=settings().cookie_secure, samesite="strict", path="/")
    response.set_cookie("ca_csrf", session.csrf, max_age=max(0, int(session.expires_at)-now),
        httponly=False, secure=settings().cookie_secure, samesite="strict", path="/")


def revoke_sessions(db, user_id):
    from sqlalchemy import delete, update
    db.execute(update(RefreshToken).where(RefreshToken.user_id == user_id).values(revoked=True))
    db.execute(delete(Session).where(Session.user_id == user_id))


def issue_session(db, response: Response, user):
    from sqlalchemy import delete
    db.execute(delete(RefreshToken).where(RefreshToken.expires_at < time.time()))
    db.execute(delete(Session).where(Session.expires_at < time.time()))
    session = Session(id=secrets.token_hex(32), user_id=user.id,
        csrf=secrets.token_urlsafe(32), expires_at=time.time()+604800)
    db.add(session)
    issue_tokens(db, response, session)


def current_user(request: Request):
    with SessionLocal() as db:
        return authenticate(request, db)


def authenticate(request, db):
    raw = request.cookies.get("ca_session", "")
    session = db.get(Session, session_id(raw)) if raw else None
    if not session or session.expires_at < time.time():
        raise HTTPException(401, "Authentication required")
    user = db.get(User, session.user_id)
    if not user or not user.active:
        raise HTTPException(401, "Authentication required")
    if request.method not in ("GET", "HEAD", "OPTIONS") and not secrets.compare_digest(
        request.headers.get("X-CSRF-Token", ""), session.csrf
    ):
        raise HTTPException(403, "CSRF verification failed")
    return user


def teacher(user=Depends(current_user)):
    if user.role not in ("TEACHER", "ADMIN"):
        raise HTTPException(403, "Teacher access required")
    return user


def admin(user=Depends(current_user)):
    if user.role != "ADMIN":
        raise HTTPException(403, "Administrator access required")
    return user


def owned(entity, user):
    if entity is None or (user.role != "ADMIN" and entity.author_id != user.id):
        raise HTTPException(404, "Not found")
    return entity


def user_public(u):
    return {"id": u.id, "username": u.username, "name": u.name, "role": u.role}


def throttle(db, key, maximum, window):
    now = time.time()
    row = db.get(RateLimit, key)
    if row and row.reset_at > now:
        if row.count >= maximum:
            raise HTTPException(
                429,
                "Too many requests. Please wait.",
                headers={"Retry-After": str(max(1, int(row.reset_at - now)))},
            )
        row.count += 1
    elif row:
        row.count = 1
        row.reset_at = now + window
    else:
        db.add(RateLimit(key=key, count=1, reset_at=now + window))
