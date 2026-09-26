import hashlib
import os
import secrets
import time
from argon2 import PasswordHasher
from argon2.exceptions import VerificationError, InvalidHashError
from fastapi import Depends, HTTPException, Request, Response
from .db import SessionLocal
from .models import User, Session, RateLimit

hasher = PasswordHasher(time_cost=2, memory_cost=19456, parallelism=1)
DUMMY_HASH = hasher.hash(secrets.token_urlsafe(32))
COOKIE_SECURE = os.getenv("COOKIE_SECURE", "false").lower() == "true"


def hash_password(password):
    return hasher.hash(password)


def verify_password(password, hashed):
    try:
        return hasher.verify(hashed, password)
    except (VerificationError, InvalidHashError):
        return False


def session_id(raw):
    return hashlib.sha256(raw.encode()).hexdigest()


def issue_session(db, response: Response, user):
    raw = secrets.token_urlsafe(40)
    csrf = secrets.token_urlsafe(32)
    db.add(
        Session(
            id=session_id(raw),
            user_id=user.id,
            csrf=csrf,
            expires_at=time.time() + 86400,
        )
    )
    response.set_cookie(
        "ca_session",
        raw,
        max_age=86400,
        httponly=True,
        secure=COOKIE_SECURE,
        samesite="strict",
        path="/",
    )
    response.set_cookie(
        "ca_csrf",
        csrf,
        max_age=86400,
        httponly=False,
        secure=COOKIE_SECURE,
        samesite="strict",
        path="/",
    )


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
