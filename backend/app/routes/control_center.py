import time
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import select
from sqlalchemy.orm import Session
from ..db import get_db, lock_write
from ..models import Contest, Submission, PuzzleReward, AuditLog, RejudgeBatch
from ..schemas import DisplaySettings, RejudgeIn, LogoIn, TeamsCSV, ContestLanguages
from ..security import teacher, current_user, owned
from ..services.access import access_contest, contest_status, manager, problem_pairs
from ..services.scoreboard import scoreboard, freeze_cutoff
from ..services.control_center import control_data, identities
from ..services.contest_events import emit, touch_presence
from ..services.rejudging import create_batch

router = APIRouter()


@router.get("/server")
def server_address(request: Request, user=Depends(teacher)):
    import os, ipaddress

    host = os.getenv("CODEARENA_LAN_HOST", "")
    try:
        address = ipaddress.ip_address(host)
        if address.is_loopback or address.is_unspecified:
            host = ""
    except ValueError:
        host = ""
    origin = str(request.base_url).rstrip("/")
    if host:
        origin = f"{request.url.scheme}://{host}:{os.getenv('PUBLIC_PORT', '8000')}"
    return {"address": origin, "detected": bool(host)}


@router.post("/teams/prepare", status_code=201)
def prepare_teams(req: TeamsCSV, user=Depends(teacher), db: Session = Depends(get_db)):
    import csv, io, secrets
    from ..models import User
    from ..security import hash_password

    reader = csv.DictReader(io.StringIO(req.csv.lstrip("\ufeff")))
    if reader.fieldnames != [
        "team_name",
        "organization",
        "member1",
        "member2",
        "member3",
    ]:
        raise HTTPException(
            422, "CSV columns: team_name,organization,member1,member2,member3"
        )
    rows = list(reader)
    if not 1 <= len(rows) <= 100:
        raise HTTPException(422, "Import 1–100 teams")
    names = set()
    prepared = []
    for row in rows:
        if None in row or any(v is None for v in row.values()):
            raise HTTPException(422, "Invalid CSV row")
        name = row["team_name"].strip()
        organization = row["organization"].strip()
        members = [
            row[f"member{i}"].strip() for i in (1, 2, 3) if row[f"member{i}"].strip()
        ]
        if (
            not 1 <= len(name) <= 100
            or len(organization) > 120
            or not members
            or any(not 2 <= len(m) <= 100 for m in members)
            or name.casefold() in names
        ):
            raise HTTPException(422, "Invalid or duplicate team/member name")
        names.add(name.casefold())
        prepared.append((name, organization, members))
    # Hash outside the SQLite write transaction; never store plaintext passwords.
    accounts = []
    for name, organization, members in prepared:
        for member in members:
            password = secrets.token_urlsafe(12)
            accounts.append(
                (
                    name,
                    organization,
                    member,
                    "team_" + secrets.token_hex(6),
                    password,
                    hash_password(password),
                )
            )
    lock_write(db)
    teams = {
        name: {"name": name, "organization": organization, "user_ids": []}
        for name, organization, _ in prepared
    }
    credentials = []
    for name, organization, member, username, password, hashed in accounts:
        account = User(
            username=username,
            name=member,
            role="STUDENT",
            creator_id=user.id,
            password_hash=hashed,
        )
        db.add(account)
        db.flush()
        teams[name]["user_ids"].append(account.id)
        credentials.append(
            {"team": name, "name": member, "username": username, "password": password}
        )
    from ..services.common import audit

    audit(
        db,
        user,
        "teams.prepare",
        detail={"teams": len(teams), "accounts": len(accounts)},
    )
    db.commit()
    return {"teams": list(teams.values()), "credentials": credentials}


@router.post("/contests/{cid}/logo")
def logo(cid: int, req: LogoIn, user=Depends(teacher), db: Session = Depends(get_db)):
    import base64, io, warnings
    from PIL import Image

    c = owned(db.get(Contest, cid), user)
    data = ""
    if req.data:
        try:
            if not req.data.startswith(
                (
                    "data:image/png;base64,",
                    "data:image/jpeg;base64,",
                    "data:image/webp;base64,",
                )
            ):
                raise ValueError()
            raw = base64.b64decode(req.data.split(",", 1)[1], validate=True)
            if len(raw) > 500000:
                raise ValueError()
            with warnings.catch_warnings():
                warnings.simplefilter("error", Image.DecompressionBombWarning)
                with Image.open(io.BytesIO(raw)) as source:
                    if (
                        source.width * source.height > 4000000
                        or getattr(source, "n_frames", 1) != 1
                    ):
                        raise ValueError()
                    source.load()
                    source.thumbnail((1000, 1000))
                    safe = source.convert("RGB")
                    output = io.BytesIO()
                    safe.save(output, format="JPEG", quality=85)
            data = (
                "data:image/jpeg;base64," + base64.b64encode(output.getvalue()).decode()
            )
        except Exception:
            raise HTTPException(
                422, "Use a static PNG/JPEG/WebP, up to 500 KB and 4 megapixels"
            ) from None
    c.logo_data = data
    emit(db, cid, "contest.logo", cid, user=user)
    db.commit()
    return {"logo_data": data}


def public_contest(db, cid):
    c = db.get(Contest, cid)
    if (
        not c
        or not c.public_scoreboard
        or not c.scoreboard_enabled
        or contest_status(c) in ("DRAFT", "SCHEDULED", "ARCHIVED")
    ):
        raise HTTPException(404, "Public display is unavailable")
    return c


@router.get("/contests/{cid}/control")
def control(cid: int, user=Depends(teacher), db: Session = Depends(get_db)):
    return control_data(db, owned(db.get(Contest, cid), user), user)


@router.post("/contests/{cid}/presence")
def presence(cid: int, user=Depends(current_user), db: Session = Depends(get_db)):
    lock_write(db)
    c = access_contest(db, cid, user)
    if user.role == "STUDENT":
        touch_presence(db, c, user)
    db.commit()
    return {"ok": True}


@router.patch("/contests/{cid}/display")
def display(
    cid: int, req: DisplaySettings, user=Depends(teacher), db: Session = Depends(get_db)
):
    lock_write(db)
    c = owned(db.get(Contest, cid), user)
    c.public_scoreboard = req.public_scoreboard
    emit(db, cid, "contest.display", cid, {"enabled": req.public_scoreboard}, user)
    db.commit()
    return {"public_scoreboard": c.public_scoreboard}


@router.get("/public/contests/{cid}/scoreboard")
def public_board(cid: int, db: Session = Depends(get_db)):
    return scoreboard(db, public_contest(db, cid), public=True)


@router.get("/contests/{cid}/public-scoreboard")
def board_preview(cid: int, user=Depends(current_user), db: Session = Depends(get_db)):
    return scoreboard(db, access_contest(db, cid, user), user, public=True)


@router.get("/contests/{cid}/replay")
def replay(
    cid: int,
    elapsed: float = Query(0, ge=0),
    user=Depends(current_user),
    db: Session = Depends(get_db),
):
    c = access_contest(db, cid, user)
    if contest_status(c) != "FINISHED":
        raise HTTPException(409, "Replay is available after finish")
    if not manager(c, user) and freeze_cutoff(c) is not None:
        raise HTTPException(403, "Replay is hidden until unfreeze")
    finished = []
    for s in db.scalars(
        select(Submission).where(
            Submission.contest_id == cid,
            Submission.kind == "SUBMIT",
            Submission.is_practice.is_(False),
        )
    ):
        original = [h["finished_at"] for h in (s.history or []) if h.get("finished_at")]
        if s.finished_at:
            original.append(s.finished_at)
        if original:
            finished.append(min(original))
    duration = max(0, max([c.end_time, *finished]) - c.start_time)
    at = c.start_time + min(elapsed, duration)
    return {
        "duration": duration,
        "elapsed": min(elapsed, duration),
        "board": scoreboard(db, c, user, at=at),
        "events": [
            {"id": e.id, "type": e.action, "time": e.created_at, "detail": e.detail}
            for e in db.scalars(
                select(AuditLog)
                .where(AuditLog.contest_id == cid, AuditLog.created_at <= at)
                .order_by(AuditLog.id.desc())
                .limit(20)
            )
        ]
        if manager(c, user)
        else [],
    }


@router.post("/contests/{cid}/reveal")
def reveal(cid: int, user=Depends(teacher), db: Session = Depends(get_db)):
    lock_write(db)
    c = owned(db.get(Contest, cid), user)
    if contest_status(c) != "FINISHED" or freeze_cutoff(c) is None:
        raise HTTPException(409, "Finish and freeze the contest before reveal")
    if db.scalar(
        select(Submission.id)
        .where(
            Submission.contest_id == cid, Submission.status.in_(["QUEUED", "RUNNING"])
        )
        .limit(1)
    ) or db.scalar(
        select(RejudgeBatch.id).where(
            RejudgeBatch.contest_id == cid, RejudgeBatch.finished_at.is_(None)
        )
    ):
        raise HTTPException(409, "Wait for judging and rejudge batches to finish")
    board = scoreboard(db, c, user, public=True)
    choice = next(
        (
            (row, cell)
            for row in reversed(board["rows"])
            for cell in row["cells"]
            if cell["pending"]
        ),
        None,
    )
    if choice is None:
        return {"done": True, "board": board}
    row, cell = choice
    query = select(Submission).where(
        Submission.contest_id == cid,
        Submission.problem_id == cell["problem_id"],
        Submission.kind == "SUBMIT",
        Submission.is_practice.is_(False),
    )
    query = (
        query.where(Submission.team_id == row["team_id"])
        if c.mode == "TEAM"
        else query.where(Submission.user_id == row["user_id"])
    )
    ids = [s.id for s in db.scalars(query)]
    c.revealed_ids = sorted(set(c.revealed_ids or []) | set(ids))
    emit(
        db,
        cid,
        "scoreboard.reveal",
        cell["problem_id"],
        {"name": row["name"], "letter": cell["letter"]},
        user,
    )
    db.commit()
    return {
        "done": False,
        "revealed": {"name": row["name"], "letter": cell["letter"]},
        "board": scoreboard(db, c, user, public=True),
    }


@router.post("/contests/{cid}/rejudge", status_code=202)
def rejudge_contest(
    cid: int, req: RejudgeIn, user=Depends(teacher), db: Session = Depends(get_db)
):
    lock_write(db)
    c = owned(db.get(Contest, cid), user)
    if req.problem_id and req.problem_id not in [p.id for p, _ in problem_pairs(db, c)]:
        raise HTTPException(404, "Problem not found")
    batch = create_batch(db, c, user, req.problem_id, req.affected_only)
    db.commit()
    return {"id": batch.id, "total": batch.total}


def puzzle_desk(db, c):
    teams = {t["identity"]: t for t in identities(db, c)}
    letters = {p.id: chr(65 + cp.ordinal) for p, cp in problem_pairs(db, c)}
    return [
        {
            "id": r.id,
            "name": teams.get(r.identity, {}).get("name", r.identity),
            "identity": r.identity,
            "problem_id": r.problem_id,
            "letter": letters.get(r.problem_id),
            "solved_at": r.solved_at,
            "status": "DELIVERED" if r.delivered_at else "WAITING",
            "delivered_at": r.delivered_at,
            "delivered_by": r.delivered_by,
            "revoked": r.revoked,
        }
        for r in db.scalars(
            select(PuzzleReward)
            .where(PuzzleReward.contest_id == c.id)
            .order_by(PuzzleReward.solved_at)
        )
    ]


@router.get("/contests/{cid}/puzzles")
def puzzles(cid: int, user=Depends(teacher), db: Session = Depends(get_db)):
    return puzzle_desk(db, owned(db.get(Contest, cid), user))


@router.post("/puzzles/{rid}/delivered")
def delivered(rid: int, user=Depends(teacher), db: Session = Depends(get_db)):
    lock_write(db)
    reward = db.get(PuzzleReward, rid)
    if reward is None:
        raise HTTPException(404, "Reward not found")
    owned(db.get(Contest, reward.contest_id), user)
    if reward.revoked:
        raise HTTPException(409, "Acceptance was revoked by rejudge")
    if reward.delivered_at is None:
        reward.delivered_at = time.time()
        reward.delivered_by = user.id
        emit(db, reward.contest_id, "puzzle.delivered", rid, user=user)
    db.commit()
    return {"ok": True}


@router.get("/network/windows-script")
def windows_network_script(user=Depends(teacher)):
    from pathlib import Path
    from fastapi.responses import FileResponse

    return FileResponse(
        Path(__file__).resolve().parents[1] / "assets" / "WindowsContestNetwork.ps1",
        media_type="text/plain",
        filename="WindowsContestNetwork.ps1",
    )


@router.patch("/contests/{cid}/languages")
def set_languages(
    cid: int,
    req: ContestLanguages,
    user=Depends(teacher),
    db: Session = Depends(get_db),
):
    lock_write(db)
    c = owned(db.get(Contest, cid), user)
    if contest_status(c) in ("RUNNING", "PAUSED"):
        raise HTTPException(409, "Language changes are locked during an active contest")
    c.languages = list(dict.fromkeys(req.languages))
    emit(db, cid, "contest.languages", cid, {"languages": c.languages}, user)
    db.commit()
    return {"languages": c.languages}
