"""Exercise the checked-in migration, including downgrade, on a temporary DB."""

import os
from pathlib import Path
import sqlite3
import subprocess
import sys


def test_initial_schema_roundtrip(tmp_path):
    root = Path(__file__).resolve().parents[1]
    database = tmp_path / "migration.db"
    env = dict(os.environ, DATABASE_URL=f"sqlite:///{database.as_posix()}")
    command = [sys.executable, "-m", "alembic", "-c", str(root / "backend/alembic.ini")]
    subprocess.run(
        command + ["upgrade", "head"], env=env, check=True, capture_output=True
    )
    with sqlite3.connect(database) as db:
        tables = {
            r[0]
            for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")
        }
        assert {
            "users",
            "contests",
            "submissions",
            "submission_test_results",
            "audit_logs",
        } <= tables
        assert db.execute("SELECT version_num FROM alembic_version").fetchone() == (
            "0002",
        )
        assert "request_id" in {
            r[1] for r in db.execute("PRAGMA table_info(submissions)")
        }
    subprocess.run(
        command + ["downgrade", "base"], env=env, check=True, capture_output=True
    )
    with sqlite3.connect(database) as db:
        tables = {
            r[0]
            for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")
        }
        assert "users" not in tables
