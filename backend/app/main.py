import asyncio
import hashlib
import json
import os
import time
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from sqlalchemy import select, func, or_
from sqlalchemy.exc import IntegrityError
from .db import SessionLocal
from .models import Announcement, Clarification, Session, Submission, User
from .security import session_id
from .services import access_contest, contest_status, iso, manager
from .services.execution import execution_policy
from .config import settings
from .middleware.logging import configure_logging, event
from .middleware.limits import limiter
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware


@asynccontextmanager
async def lifespan(app):
    settings()  # Fail closed when the signing key/configuration is absent or invalid.
    configure_logging()
    yield


app = FastAPI(
    title="CodeArena", version="3.4.0", lifespan=lifespan, docs_url=None, redoc_url=None
)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)
origins = [o.strip() for o in os.getenv("ALLOWED_ORIGINS", "").split(",") if o.strip()]
if origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PATCH", "DELETE"],
        allow_headers=["Content-Type", "X-CSRF-Token"],
    )


@app.middleware("http")
async def security_headers(request, call_next):
    if request.method in ("POST", "PATCH", "PUT", "DELETE"):
        origin = request.headers.get("origin")
        allowed = set(origins) | {str(request.base_url).rstrip("/")}
        if origin and origin not in allowed:
            return JSONResponse({"detail": "Origin not allowed"}, status_code=403)
        size = request.headers.get("content-length")
        if size and (not size.isdigit() or int(size) > 10 * 1024 * 1024):
            return JSONResponse({"detail": "Request body too large"}, status_code=413)
        # Bound streamed bodies too; do not trust Content-Length alone.
        total = 0
        chunks = []
        async for chunk in request.stream():
            total += len(chunk)
            if total > 10 * 1024 * 1024:
                return JSONResponse(
                    {"detail": "Request body too large"}, status_code=413
                )
            chunks.append(chunk)
        request._body = b"".join(chunks)
    return await call_next(request)


@app.middleware("http")
async def response_security(request, call_next):
    try:
        response = await call_next(request)
    except Exception:
        response = JSONResponse({"detail": "Internal service error"}, status_code=500)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    response.headers["Strict-Transport-Security"] = "max-age=31536000"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers.setdefault(
        "Content-Security-Policy",
        (
            "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; font-src 'self'; img-src 'self' data:; connect-src 'self' ws: wss:; worker-src 'self' blob:; frame-ancestors 'none'; base-uri 'self'; form-action 'self'"
        ),
    )
    if request.url.path.startswith("/api/"):
        response.headers["Cache-Control"] = "no-store"
    if response.status_code >= 400:
        route = request.scope.get("route")
        event(
            "http.error",
            method=request.method,
            route=getattr(route, "path", "unmatched"),
            status=response.status_code,
        )
    return response


@app.exception_handler(IntegrityError)
async def integrity_error(request, exc):
    return JSONResponse(
        {"detail": "Duplicate value or invalid reference"}, status_code=409
    )


@app.exception_handler(RequestValidationError)
async def validation_error(request, exc):
    return JSONResponse(
        {
            "detail": "; ".join(
                ".".join(map(str, e["loc"])) + ": " + e["msg"] for e in exc.errors()
            )
        },
        status_code=422,
    )


@app.exception_handler(Exception)
async def safe_error(request, exc):
    # Do not echo source, database paths, credentials, or stack traces.
    return JSONResponse({"detail": "Internal service error"}, status_code=500)


from .routes import (
    auth,
    users,
    problems,
    contests,
    submissions,
    communication,
    operations,
    control_center,
)

for route in (
    auth,
    users,
    problems,
    contests,
    submissions,
    communication,
    operations,
    control_center,
):
    app.include_router(route.router, prefix="/api/v1")


@app.websocket("/ws/contests/{cid}")
async def contest_ws(ws: WebSocket, cid: int):
    # Scoped invalidation stream: REST remains authoritative. Re-check both
    # session and membership on each tick; never send source/hidden tests.
    origin = ws.headers.get("origin")
    expected = (
        ("https" if ws.url.scheme == "wss" else "http")
        + "://"
        + ws.headers.get("host", "")
    )
    if not origin or origin not in set(origins) | {expected}:
        await ws.close(code=4403)
        return

    def snapshot():
        with SessionLocal() as db:
            session = db.get(Session, session_id(ws.cookies.get("ca_session", "")))
            if not session or session.expires_at < time.time():
                raise HTTPException(401)
            u = db.get(User, session.user_id)
            if not u or not u.active:
                raise HTTPException(401)
            c = access_contest(db, cid, u)
            from .models import AuditLog
            from .services.scoreboard import freeze_cutoff
            from .services.scoreboard import scoreboard

            visible_revision = None
            if c.scoreboard_enabled and contest_status(c) in (
                "RUNNING",
                "PAUSED",
                "FINISHED",
            ):
                board = scoreboard(db, c, u)
                visible_revision = hashlib.sha256(
                    json.dumps(board["rows"], sort_keys=True).encode()
                ).hexdigest()
            q = select(Submission.id, Submission.status).where(
                Submission.contest_id == cid
            )
            if not manager(c, u):
                q = q.where(Submission.user_id == u.id)
            subs = [
                {"id": sid, "status": status}
                for sid, status in db.execute(
                    q.order_by(Submission.id.desc()).limit(50)
                )
            ]
            clarification_query = select(func.max(Clarification.updated_at)).where(
                Clarification.contest_id == cid
            )
            from .services.access import conversation_user_ids

            if not manager(c, u):
                clarification_query = clarification_query.where(
                    or_(
                        Clarification.user_id.in_(conversation_user_ids(db, c, u)),
                        Clarification.is_public == True,
                    )
                )
            from .services.participation import completed

            completion = completed(db, c, u) if u.role == "STUDENT" else None
            return {
                "participation_completed": completion.completed_at
                if completion
                else None,
                "type": "contest.updated",
                "status": contest_status(c),
                "execution": execution_policy(db, c),
                "end_time": iso(c.end_time),
                "frozen": freeze_cutoff(c) is not None,
                "revision": db.scalar(
                    select(func.max(AuditLog.id)).where(AuditLog.contest_id == cid)
                )
                if manager(c, u)
                else None,
                "reveal_revision": len(c.revealed_ids or []),
                "standings_revision": visible_revision,
                "server_time": iso(time.time()),
                "submissions": subs,
                "announcement_count": db.scalar(
                    select(func.count())
                    .select_from(Announcement)
                    .where(Announcement.contest_id == cid)
                ),
                "clarification_revision": db.scalar(clarification_query) or 0,
            }

    try:
        first = await asyncio.to_thread(snapshot)
        await ws.accept()
        await ws.send_json(first)
        while True:
            await asyncio.sleep(2)
            await ws.send_json(await asyncio.to_thread(snapshot))
    except HTTPException:
        await ws.close(code=4403)
    except (WebSocketDisconnect, RuntimeError):
        pass


@app.websocket("/ws/public/contests/{cid}")
async def public_contest_ws(ws: WebSocket, cid: int):
    expected = (
        ("https" if ws.url.scheme == "wss" else "http")
        + "://"
        + ws.headers.get("host", "")
    )
    if ws.headers.get("origin") not in set(origins) | {expected}:
        await ws.close(code=4403)
        return

    def public_snapshot():
        from .routes.control_center import public_contest
        from .services.scoreboard import scoreboard

        with SessionLocal() as db:
            board = scoreboard(db, public_contest(db, cid), public=True)
            board.pop("server_time", None)
            return {
                "revision": hashlib.sha256(
                    json.dumps(board, sort_keys=True).encode()
                ).hexdigest()
            }

    try:
        first = await asyncio.to_thread(public_snapshot)
        await ws.accept()
        await ws.send_json(first)
        while True:
            await asyncio.sleep(3)
            await ws.send_json(await asyncio.to_thread(public_snapshot))
    except HTTPException:
        await ws.close(code=4403)
    except (WebSocketDisconnect, RuntimeError):
        pass


dist = Path(__file__).resolve().parents[2] / "frontend" / "dist"
if dist.exists():
    app.mount("/assets", StaticFiles(directory=dist / "assets"), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    def spa(path: str):
        if path.startswith(("api/", "ws/", "static/")):
            raise HTTPException(404, "Not found")
        target = dist / path
        if target.is_file() and dist.resolve() in target.resolve().parents:
            return FileResponse(target)
        return FileResponse(dist / "index.html")
