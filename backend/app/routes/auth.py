import time
import secrets
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy import select, delete, func
from sqlalchemy.orm import Session as DBSession
from ..db import get_db, lock_write
from ..models import Session, SystemSetting, User, RefreshToken
from .. import schemas as S
from ..security import (
    current_user,
    user_public,
    hash_password,
    verify_password,
    issue_session,
    session_id,
    throttle,
    DUMMY_HASH,
    decode_token, issue_tokens, revoke_sessions,
)
from ..services import audit, judge_status
from ..middleware.limits import limiter

router = APIRouter()


@router.get("/health")
@limiter.exempt
def health(db: DBSession = Depends(get_db)):
    db.execute(select(1))
    return {"status": "ok", **judge_status(db)}


@router.get("/system/health")
@limiter.exempt
def system_health(db: DBSession = Depends(get_db)):
    return health(db)


@router.get("/auth/status")
def auth_status(db: DBSession = Depends(get_db)):
    setting = db.get(SystemSetting, "organization")
    return {
        "setup_required": db.scalar(
            select(func.count()).select_from(User).where(User.role == "ADMIN")
        )
        == 0,
        "organization": setting.value if setting else "CodeArena",
        **judge_status(db),
    }


@router.post("/auth/setup", status_code=201)
@limiter.limit("5/minute")
def setup(req: S.Setup, request: Request, response: Response, db: DBSession = Depends(get_db)):
    lock_write(db)
    if db.scalar(select(func.count()).select_from(User)):
        raise HTTPException(409, "Setup is already complete")
    user = User(
        username=req.username,
        name=req.name,
        password_hash=hash_password(req.password),
        role="ADMIN",
    )
    db.add(user)
    db.flush()
    db.add(SystemSetting(key="organization", value=req.organization))
    db.add(SystemSetting(key="language", value=req.language))
    issue_session(db, response, user)
    audit(db, user, "system.setup")
    db.commit()
    return user_public(user)


@router.post("/auth/login")
@limiter.limit("5/minute")
def login(
    req: S.Login, request: Request, response: Response, db: DBSession = Depends(get_db)
):
    lock_write(db)
    peer = request.client.host if request.client else "unknown"
    throttle(db, "login:" + peer, 5, 900)
    db.commit()  # Failed login attempts persist as well.
    # Serialize verification/session creation with administrative password resets.
    lock_write(db)
    user = db.scalar(select(User).where(User.username == req.username))
    valid = verify_password(req.password, user.password_hash if user else DUMMY_HASH)
    if not valid or not user or not user.active:
        audit(db, None, "auth.login_failed")
        db.commit()
        raise HTTPException(401, "Invalid username or password")
    if user.password_hash.startswith("$argon2") and len(req.password.encode()) <= 72:
        user.password_hash = hash_password(req.password)
    issue_session(db, response, user)
    audit(db, user, "auth.login")
    user.last_seen = time.time()
    db.commit()
    return user_public(user)


@router.post("/auth/refresh")
@limiter.limit("5/minute")
def refresh(request: Request, response: Response, db: DBSession = Depends(get_db)):
    claims = decode_token(request.cookies.get("ca_refresh", ""), "refresh")
    lock_write(db)
    record = db.get(RefreshToken, claims["jti"])
    session = db.get(Session, claims["sid"])
    if not record or not session or record.session_id != session.id or session.expires_at <= time.time():
        raise HTTPException(401, "Authentication required")
    if not secrets.compare_digest(request.headers.get("X-CSRF-Token", ""), session.csrf):
        raise HTTPException(403, "CSRF verification failed")
    if record.revoked:
        revoke_sessions(db, session.user_id)
        audit(db, None, "auth.refresh_replay")
        db.commit()
        raise HTTPException(401, "Authentication required")
    user = db.get(User, session.user_id)
    if not user or not user.active or claims["sub"] != str(user.id):
        raise HTTPException(401, "Authentication required")
    record.revoked = True
    issue_tokens(db, response, session)
    audit(db, user, "auth.refresh")
    db.commit()
    return {"ok": True}


@router.get("/auth/me")
def me(user=Depends(current_user)):
    return user_public(user)


@router.post("/auth/password")
@limiter.limit("5/minute")
def change_password(
    req: S.PasswordChange,
    request: Request,
    response: Response,
    user=Depends(current_user),
    db: DBSession = Depends(get_db),
):
    lock_write(db)
    u = db.get(User, user.id)
    if not verify_password(req.old_password, u.password_hash):
        raise HTTPException(400, "Current password is incorrect")
    u.password_hash = hash_password(req.new_password)
    revoke_sessions(db, u.id)
    issue_session(db, response, u)
    audit(db, user, "user.password_changed", u.id)
    db.commit()
    return {"ok": True}


@router.post("/auth/logout")
@limiter.limit("5/minute")
def logout(
    request: Request,
    response: Response,
    user=Depends(current_user),
    db: DBSession = Depends(get_db),
):
    from sqlalchemy import update
    sid = session_id(request.cookies.get("ca_session", ""))
    db.execute(update(RefreshToken).where(RefreshToken.session_id == sid).values(revoked=True))
    db.execute(
        delete(Session).where(
            Session.id == session_id(request.cookies.get("ca_session", ""))
        )
    )
    audit(db, user, "auth.logout")
    db.commit()
    response.delete_cookie("ca_session", path="/")
    response.delete_cookie("ca_refresh", path="/")
    response.delete_cookie("ca_csrf", path="/")
    return {"ok": True}
