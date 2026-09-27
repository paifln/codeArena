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
            "0007",
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


def test_teaching_upgrade_preserves_existing_submissions_and_results(tmp_path):
    from sqlalchemy import create_engine, MetaData, Integer, Float, Boolean, JSON
    root=Path(__file__).resolve().parents[1]
    database=tmp_path/'existing.db'
    env=dict(os.environ,DATABASE_URL=f'sqlite:///{database.as_posix()}')
    command=[sys.executable,'-m','alembic','-c',str(root/'backend/alembic.ini')]
    subprocess.run(command+['upgrade','0002'],env=env,check=True,capture_output=True)
    engine=create_engine(env['DATABASE_URL']);metadata=MetaData();metadata.reflect(engine)
    overrides={'users':{'username':'student','name':'Student','role':'STUDENT','password_hash':'preserve-me'},
        'contests':{'title':'History','start_time':1,'end_time':100,'status':'FINISHED'},
        'problems':{'title':'Sum','slug':'sum','difficulty':'EASY','mem_limit':128,'time_limit':1,'tags':[],'translations':{}},
        'submissions':{'source':'print(3)','language':'python3','kind':'SUBMIT','status':'ACCEPTED','problem_snapshot':{},'history':[]},
        'submission_test_results':{'verdict':'ACCEPTED','stdout':'preserved output'}}
    with engine.begin() as connection:
        for name, custom in overrides.items():
            table=metadata.tables[name];values={}
            for col in table.columns:
                if col.nullable and col.name!='id':continue
                values[col.name]= [] if isinstance(col.type,JSON) else 1 if isinstance(col.type,(Integer,Float,Boolean)) else ''
            values.update(custom);connection.execute(table.insert().values(**values))
    engine.dispose()
    subprocess.run(command+['upgrade','0003'],env=env,check=True,capture_output=True)
    with sqlite3.connect(database) as db:
        db.execute("UPDATE contests SET mode='EDUCATIONAL'")
    subprocess.run(command+['upgrade','head'],env=env,check=True,capture_output=True)
    with sqlite3.connect(database) as db:
        assert db.execute('select source,score,is_practice from submissions').fetchone()==('print(3)',100.0,0)
        assert db.execute('select stdout from submission_test_results').fetchone()==('preserved output',)
        assert db.execute('select password_hash from users').fetchone()==('preserve-me',)
        assert db.execute('select mode,scoring from contests').fetchone()==('INDIVIDUAL','EDUCATIONAL')
        assert db.execute('pragma foreign_key_check').fetchall()==[]
