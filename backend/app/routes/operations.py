import shutil
import time
import os
import re
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from ..db import get_db, DATABASE_URL
from ..models import Submission, SystemSetting
from ..security import admin
from ..services.judge_health import judge_status

router = APIRouter()


def backup_root():
    return Path(os.getenv("BACKUP_DIR", "/backups")).resolve()


@router.get("/operations/backups")
def backups(user=Depends(admin)):
    return [{"file": p.name, "size_bytes": p.stat().st_size, "time": p.stat().st_mtime}
        for p in sorted(backup_root().glob("codearena-*.db"), reverse=True)
        if re.fullmatch(r"codearena-[0-9]+\.db", p.name) and p.is_file() and not p.is_symlink()]


@router.get("/operations/backups/{filename}")
def download_backup(filename: str, user=Depends(admin)):
    if filename != os.path.basename(filename) or not re.fullmatch(r"codearena-[0-9]+\.db", filename):
        raise HTTPException(404, "Backup not found")
    path = backup_root() / filename
    if not path.is_file() or path.is_symlink() or path.resolve().parent != backup_root():
        raise HTTPException(404, "Backup not found")
    return FileResponse(path, filename=filename, media_type="application/octet-stream")


@router.get("/operations")
def operations(user=Depends(admin), db: Session = Depends(get_db)):
    now = time.time()
    pending = db.scalar(select(func.count()).select_from(Submission).where(Submission.status.in_(("QUEUED", "RUNNING"))))
    oldest = db.scalar(select(func.min(Submission.created_at)).where(Submission.status == "QUEUED"))
    errors = db.scalar(select(func.count()).select_from(Submission).where(Submission.status == "SYSTEM_ERROR", Submission.created_at > now-86400))
    path = Path(DATABASE_URL.removeprefix("sqlite:///")).resolve().parent if DATABASE_URL.startswith("sqlite:///") else Path(".")
    disk = shutil.disk_usage(path)
    backup = db.get(SystemSetting, "backup_status")
    status = backup.value if backup else None
    judge = judge_status(db)
    age = max(0, now-oldest) if oldest else 0
    alerts = []
    if not judge["judge_available"]: alerts.append("judge")
    if age > 60: alerts.append("queue")
    if errors: alerts.append("errors")
    if disk.free < 1024**3: alerts.append("disk")
    if not status or not status.get("verified") or now-status.get("time", 0) > 86400: alerts.append("backup")
    return {**judge, "pending": pending, "oldest_seconds": round(age), "system_errors_24h": errors,
            "disk_free_bytes": disk.free, "backup": status, "alerts": alerts}
