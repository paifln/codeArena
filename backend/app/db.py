import os
from pathlib import Path
from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, sessionmaker

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./data/codearena-v3.db")
if not DATABASE_URL.startswith("sqlite:///"):
    raise RuntimeError("This deployment requires SQLite WAL")
if DATABASE_URL.startswith("sqlite:///"):
    Path(DATABASE_URL.removeprefix("sqlite:///")).parent.mkdir(
        parents=True, exist_ok=True
    )
engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False, "timeout": 10}
    if DATABASE_URL.startswith("sqlite")
    else {},
    pool_pre_ping=True,
)
if DATABASE_URL.startswith("sqlite"):

    @event.listens_for(engine, "connect")
    def sqlite_settings(conn, _):
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("PRAGMA busy_timeout=10000")
        conn.execute("PRAGMA synchronous=NORMAL")


class Base(DeclarativeBase):
    pass


SessionLocal = sessionmaker(engine, expire_on_commit=False)


def get_db():
    with SessionLocal() as session:
        yield session


def lock_write(db):
    # Call before any read in a state-changing transaction. Serializes SQLite
    # admission/state transitions without a process-local lock.
    if db.get_bind().dialect.name == "sqlite":
        from sqlalchemy import text

        db.execute(text("BEGIN IMMEDIATE"))
