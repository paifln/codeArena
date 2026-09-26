# Operations

## Stop and inspect

Run `docker compose stop` to stop API and worker while retaining data. Use `docker compose ps -a` and `docker compose logs --tail=100 api worker` for diagnosis. Do not remove the data volume when preserving the installation.

The API health check measures HTTP availability. Worker health measures fresh, available judge heartbeat. An unavailable worker causes admission to fail closed.

## Restore a backup

First preserve a fresh copy of the current database using the README backup procedure. Verify that the intended backup file exists, and stop API and worker. The following operation replaces the database contents with the backup:

```sh
docker compose stop api worker
docker compose run --rm --no-deps -v ./codearena-backup.db:/backup.db:ro api python -c "import sqlite3; a=sqlite3.connect('file:/backup.db?mode=ro', uri=True); b=sqlite3.connect('/data/codearena-v3.db'); a.backup(b); b.close(); a.close()"
docker compose run --rm --no-deps api python -m app.migrate
docker compose up -d
```

Use an application version compatible with the backup schema. Check SQLite integrity, sign-in, contest data and a test submission before admitting students. Rehearse on an isolated installation, not on the only copy of institutional data.

## Before an assessment

Check available disk space, recent backup, fresh worker heartbeat, classroom network access and time synchronization. Rehearse one student Run and Submit, verify hidden diagnostics remain private, and confirm contest times/participants. Define who can pause a contest and how students report an outage.

## Incident handling

Pause the affected contest when appropriate, record timing and preserve logs without exposing credentials or student source. Inspect worker and sandbox health before resuming. A network timeout may occur after admission: consult submission history before re-entering code. Restart recovery uses leases; do not edit queue rows manually.
