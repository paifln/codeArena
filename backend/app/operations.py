from contextlib import closing
"""Consistent backups, restore verification and a small supervised scheduler."""
import argparse
import json
import logging
import os
from pathlib import Path
import signal
import sqlite3
import tempfile
import threading
import time

from .db import DATABASE_URL, SessionLocal
from .models import SystemSetting
from .middleware.logging import configure_logging, event


def verify_restore(backup):
    with tempfile.TemporaryDirectory() as folder:
        with closing(sqlite3.connect(f"file:{Path(backup).resolve().as_posix()}?mode=ro&immutable=1", uri=True)) as source:
            with closing(sqlite3.connect(str(Path(folder) / "restored.db"))) as restored:
                source.backup(restored)
                if restored.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                    raise RuntimeError("Restored backup failed integrity check")
                if restored.execute("PRAGMA foreign_key_check").fetchall():
                    raise RuntimeError("Restored backup failed foreign key check")
                counts = {}
                for table in ("users", "contests", "submissions"):
                    counts[table] = restored.execute(f"SELECT count(*) FROM {table}").fetchone()[0]
                    if counts[table] != source.execute(f"SELECT count(*) FROM {table}").fetchone()[0]:
                        raise RuntimeError("Restored row count mismatch")
                return counts


def backup_database(database, directory, keep=28):
    root = Path(directory).resolve()
    root.mkdir(parents=True, exist_ok=True)
    target = root / f"codearena-{time.time_ns()}.db"
    with closing(sqlite3.connect(f"file:{Path(database).resolve().as_posix()}?mode=ro", uri=True)) as source:
        with closing(sqlite3.connect(target)) as destination:
            source.backup(destination)
    counts = verify_restore(target)
    # Only rotate files produced by this scheduler, after a verified successful backup.
    candidates = sorted((p for p in root.glob("codearena-*.db") if p.stem.removeprefix("codearena-").isdigit()), key=lambda p: p.name, reverse=True)
    for old in candidates[max(1, keep):]:
        if old.parent == root and not old.is_symlink():
            old.unlink()
    return {"file": target.name, "time": time.time(), "verified": True, "counts": counts, "size_bytes": target.stat().st_size}


def record(value):
    with SessionLocal() as db:
        setting = db.get(SystemSetting, "backup_status")
        if setting:
            setting.value = value
        else:
            db.add(SystemSetting(key="backup_status", value=value))
        db.commit()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--verify")
    args = parser.parse_args()
    if args.verify:
        print(json.dumps(verify_restore(args.verify)))
        return
    stopped = threading.Event()
    signal.signal(signal.SIGTERM, lambda *_: stopped.set())
    signal.signal(signal.SIGINT, lambda *_: stopped.set())
    configure_logging()
    while not stopped.is_set():
        try:
            if not DATABASE_URL.startswith("sqlite:///"):
                raise RuntimeError("This backup service supports SQLite only")
            result = backup_database(DATABASE_URL.removeprefix("sqlite:///"),
                os.environ.get("BACKUP_DIR", "/backups"), int(os.environ.get("BACKUP_KEEP", "28")))
            record(result)
            event("backup.verified", file=result["file"], size_bytes=result["size_bytes"])
        except Exception:
            logging.exception("Backup failed")
            record({"time": time.time(), "verified": False, "error": "Backup or restore verification failed; inspect backup service logs"})
            if args.once:
                raise
        if args.once:
            break
        stopped.wait(max(60, int(os.environ.get("BACKUP_INTERVAL_SECONDS", "21600"))))


if __name__ == "__main__":
    main()
