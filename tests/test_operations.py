import sqlite3
from app.operations import backup_database, verify_restore


def test_backup_restore_and_rotation_only_touch_scheduler_files(tmp_path):
    source=tmp_path/'source.db'
    with sqlite3.connect(source) as db:
        for table in ('users','contests','submissions'):
            db.execute(f'CREATE TABLE {table} (id INTEGER PRIMARY KEY)')
            db.execute(f'INSERT INTO {table} VALUES (1)')
    backups=tmp_path/'backups';backups.mkdir()
    unrelated=backups/'manual-copy.db';unrelated.write_text('keep')
    first=backup_database(source,backups,keep=1)
    second=backup_database(source,backups,keep=1)
    assert second['verified'] and second['counts']['users']==1
    assert not (backups/first['file']).exists()
    assert unrelated.read_text()=='keep'
    assert verify_restore(backups/second['file'])['submissions']==1
