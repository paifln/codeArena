import time
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy import select, delete, func
from sqlalchemy.orm import Session as DBSession
from ..db import get_db, lock_write
from ..models import Session, SystemSetting, User
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
)
from ..services import audit, judge_status

router = APIRouter()


@router.get("/health")
def health(db: DBSession = Depends(get_db)):
    db.execute(select(1))
    return {"status": "ok", **judge_status(db)}


@router.get("/system/health")
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
def setup(req: S.Setup, response: Response, db: DBSession = Depends(get_db)):
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
def login(
    req: S.Login, request: Request, response: Response, db: DBSession = Depends(get_db)
):
    lock_write(db)
    peer = request.client.host if request.client else "unknown"
    throttle(db, "login:" + peer, 20, 60)
    db.commit()  # Failed login attempts persist as well.
    user = db.scalar(select(User).where(User.username == req.username))
    valid = verify_password(req.password, user.password_hash if user else DUMMY_HASH)
    if not valid or not user or not user.active:
        raise HTTPException(401, "Invalid username or password")
    issue_session(db, response, user)
    user.last_seen = time.time()
    db.commit()
    return user_public(user)


@router.get("/auth/me")
def me(user=Depends(current_user)):
    return user_public(user)


@router.post("/auth/password")
def change_password(
    req: S.PasswordChange,
    response: Response,
    user=Depends(current_user),
    db: DBSession = Depends(get_db),
):
    u = db.get(User, user.id)
    if not verify_password(req.old_password, u.password_hash):
        raise HTTPException(400, "Current password is incorrect")
    u.password_hash = hash_password(req.new_password)
    db.execute(delete(Session).where(Session.user_id == u.id))
    issue_session(db, response, u)
    audit(db, user, "user.password_changed", u.id)
    db.commit()
    return {"ok": True}


@router.post("/auth/logout")
def logout(
    request: Request,
    response: Response,
    user=Depends(current_user),
    db: DBSession = Depends(get_db),
):
    db.execute(
        delete(Session).where(
            Session.id == session_id(request.cookies.get("ca_session", ""))
        )
    )
    db.commit()
    response.delete_cookie("ca_session", path="/")
    response.delete_cookie("ca_csrf", path="/")
    return {"ok": True}
