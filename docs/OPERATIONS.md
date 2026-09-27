# Operations

## Signing key and authentication upgrade

Initialize `.env` with `python tools/init_env.py` before Compose startup. Keep this
file private and backed up separately. Migration 0004 preserves accounts/results,
converts existing educational contests to independent scoring, and ends old
sessions. Users sign in again with their existing passwords. Rotating SECRET_KEY
also invalidates all JWTs; never rotate it silently during normal restarts.

Limits are per client IP. With a reverse proxy, explicitly trust only that proxy's
address when forwarding client IPs. A shared NAT address shares the login/request
quota. Rehearse the classroom's actual network topology before an assessment.

## Stop and inspect

Run `docker compose stop` to stop API and worker while retaining data. Use `docker compose ps -a` and `docker compose logs --tail=100 api worker` for diagnosis. Do not remove the data volume when preserving the installation.

The API health check measures HTTP availability. Worker health measures fresh, available judge heartbeat. An unavailable worker causes admission to fail closed.

## Restore a backup

First preserve a fresh copy of the current database using the README backup procedure. Verify that the intended backup file exists, and stop API and worker. The following operation replaces the database contents with the backup:

```sh
docker compose stop api worker backup
docker compose run --rm --no-deps -v ./codearena-backup.db:/backup.db:ro api python -c "import sqlite3; a=sqlite3.connect('file:/backup.db?mode=ro&immutable=1', uri=True); b=sqlite3.connect('/data/codearena-v3.db'); a.backup(b); b.close(); a.close()"
docker compose run --rm --no-deps api python -m app.migrate
docker compose up -d
```

Use an application version compatible with the backup schema. Check SQLite integrity, sign-in, contest data and a test submission before admitting students. Rehearse on an isolated installation, not on the only copy of institutional data.

## Before an assessment

Check available disk space, recent backup, fresh worker heartbeat, classroom network access and time synchronization. Rehearse one student Run and Submit, verify hidden diagnostics remain private, and confirm contest times/participants. Define who can pause a contest and how students report an outage.

## Incident handling

Pause the affected contest when appropriate, record timing and preserve logs without exposing credentials or student source. Inspect worker and sandbox health before resuming. A network timeout may occur after admission: consult submission history before re-entering code. Restart recovery uses leases; do not edit queue rows manually.


## Automatic backups and monitoring

Backup runs immediately and every six hours by default. BACKUP_KEEP retains 28
scheduler-generated codearena-<timestamp>.db copies. Each copy is restored to a
temporary database and checked for integrity, foreign keys and core row counts.
Grant UID 10001 write access to backups/ on Linux. Verification uses a 256-MB
tmpfs by default: enlarge it for larger databases. Copy backups off-host.

Administrators open System operations for alerts: judge unavailable, queue wait
above 60 seconds, system errors in 24 hours, disk below 1 GB, or no verified
backup in 24 hours. Alerts are in-app; external delivery is not configured.
Inspect backup service logs on failure; correct permissions/capacity and retry.

## Recovery and concurrency

One worker process has two execution slots by default. JUDGE_CONCURRENCY accepts
1-4; size it to CPU/memory measurements. Expired leases retry after 300 seconds,
at most three claims before SYSTEM_ERROR. Stale workers cannot overwrite new
leases. Teachers can rejudge infrastructure errors without student penalties.

## Demo replacement

After a verified backup, stop API/worker/backup. The app.replace_demo maintenance
command takes explicit --author-id and --group-ids. It replaces only the marked
demo and selected groups, retains credentials and transfers active members.
Groups linked to another contest are rejected. --start starts a 90-minute demo.
This replaces demo history and must not be used for real assessments.
