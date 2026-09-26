# CodeArena

A self-hosted programming contest platform for schools and universities. Teachers manage problems, groups and competitions; students write Python in the browser and receive feedback from an isolated judge.

**Current scope:** one institution, one Docker host, one API process and one worker. Start with a supervised pilot and complete the [launch roadmap](docs/ROADMAP.md) before expanding.

## Features

- Administrator, teacher and student accounts with scoped permissions.
- Groups, bulk student creation and participant assignments.
- Markdown problems, samples, hidden tests and ZIP import/export.
- Scheduled contests, pause/resume, announcements and clarifications.
- Monaco editor, local drafts per account/contest/problem and custom input.
- **Run** checks samples or custom input; **Submit** checks all tests and contributes to ICPC standings.
- Live standings, scoreboard freeze, submission history and rejudging.
- Russian, Kazakh and English; light/dark themes; locally bundled fonts and editor.
- Durable queue, worker recovery and idempotent submission retries.

## Quick start

Install Docker Engine with Compose v2, or Docker Desktop in **Linux containers** mode. From the repository root:

```sh
docker compose up --build -d
docker compose ps
```

Open **http://localhost:8000** and create the first administrator. No default credentials exist; setup closes after the first administrator is created. Alternatively use `start.bat` on Windows or `sh start.sh` on Linux.

The initial build requires Internet access. Once built, classroom operation does not depend on a CDN or cloud API.

On Linux set `DOCKER_GID` in `.env` to the output of `stat -c %g /var/run/docker.sock`. Docker Desktop normally works with the default `0`.

### Teacher and student workflow

1. The administrator creates teacher accounts in people management.
2. A teacher creates a group and student accounts, assigns members and distributes individual credentials privately.
3. Create problems with sample and hidden tests; create a contest and assign groups or individual students.
4. Start the contest or publish it with a scheduled start.
5. Students sign in at the same address with their own accounts, open an assigned contest, write code, Run and Submit.

The initial setup is only for the administrator. Students do not create another installation. For classroom devices use `http://<server-LAN-IP>:8000`; localhost on a student device refers to that device. Permit the port only on the intended network.

**Paused contests intentionally reject execution.** The editor explains the reason and authorized teachers can resume from the notice. Student controls refresh automatically. An unavailable judge also disables execution with an explanation. No host execution fallback exists.

### Optional demo

After creating an administrator, use its account ID:

```sh
docker compose exec api python -m app.demo --author-id 1
```

This idempotent command creates one demo contest, no accounts and no passwords. A new demo remains a draft. Review participant assignments and start it when ready.

## Configuration and operation

Copy `.env.example` to `.env` to customize deployment.

| Variable | Purpose |
| --- | --- |
| `BIND_HOST`, `PORT` | Published interface/port; defaults to `0.0.0.0:8000` |
| `COOKIE_SECURE` | Set to true when serving through HTTPS |
| `ALLOWED_ORIGINS` | Comma-separated trusted browser origins, including scheme/port |
| `DOCKER_GID` | Group allowed to access the Docker socket |
| `RUN_COOLDOWN_SECONDS`, `SUBMIT_COOLDOWN_SECONDS` | Per-user throttling |
| `MAX_QUEUE_SIZE` | Maximum pending judge jobs |

Use a TLS reverse proxy for institutional deployment and forward WebSocket connections. Match allowed origins to the actual address. Secure cookies require HTTPS.

```sh
docker compose logs --tail=100 api worker
docker compose stop
# Start again:
docker compose up -d
```

Stopping containers preserves data. Keep the named volume when upgrading. The sandbox-image service exiting successfully is normal: it prepares an image rather than running a server.

The database is `/data/codearena-v3.db` in the Compose `arena-data` volume. Keep the same Compose project name when moving/upgrading, otherwise Compose may create a different volume. Legacy databases are not automatically converted.

### Backup and upgrade

With the API running, create a consistent SQLite backup:

```sh
docker compose exec api python -c "import sqlite3; a=sqlite3.connect('/data/codearena-v3.db'); b=sqlite3.connect('/tmp/codearena-backup.db'); a.backup(b); b.close(); a.close()"
docker compose cp api:/tmp/codearena-backup.db ./codearena-backup.db
```

Store dated copies on separate storage with restricted access: backups contain account data, student source and hidden tests. Test restoration on a separate installation. Never copy a live SQLite database alone while ignoring its WAL.

After backing up:

```sh
docker compose stop
docker compose build
docker compose run --rm --no-deps api python -m app.migrate
docker compose up -d
```

See [operations](docs/OPERATIONS.md) for restoration.

## Development and tests

Use Python 3.12+ and Node.js 22+. From the repository root:

```sh
python -m venv .venv
# Windows: .venv\Scripts\activate
# Linux: source .venv/bin/activate
pip install -r backend/requirements-dev.txt
python -m pytest tests -q
cd frontend
npm ci
npm test
npm run build
```

From `backend/`, run `python -m app.migrate`, then `uvicorn app.main:app --host 127.0.0.1 --port 8000`. From `frontend/` run `npm run dev`. Build the sandbox image from the repository root, then run `python -m judge.worker` from `backend/`. API and worker must use the same `DATABASE_URL`. Run only one worker with SQLite.

For real execution tests, from the repository root:

```sh
docker build -f Dockerfile.sandbox -t codearena-sandbox:local .
```

PowerShell:

```powershell
$env:PYTHONPATH='backend'
$env:RUN_SANDBOX_TESTS='1'
python -m pytest tests -q
```

Linux/macOS: `PYTHONPATH=backend RUN_SANDBOX_TESTS=1 python -m pytest tests -q`.

Tests use temporary databases and cover permissions, hidden-test privacy, CSRF, migrations, concurrency, pause/resume, retry deduplication, sandbox limits and the API-to-Docker-to-scoreboard flow. Vitest covers execution controls, retries, account cache isolation and drafts. CI builds the frontend and runs the checks with Docker. These checks do not establish production capacity or replace browser/accessibility review and independent security assessment.

## Architecture

```text
React / TypeScript / Monaco
         | REST + WebSocket notifications
FastAPI routes -> application services -> SQLite WAL
                                              |
                                      one judge worker
                                              |
                                 disposable Docker sandbox
```

The API authenticates and authorizes requests. It never executes submitted source and has no Docker socket. Only the worker has Docker access. See [architecture](docs/ARCHITECTURE.md) and [judge operation](backend/judge/README.md).

## Troubleshooting

| Symptom | Check |
| --- | --- |
| Run/Submit disabled | Notice explains contest state, judge availability, empty source or pending submission |
| No contests for a student | Role, group membership, assignment and publication |
| Judge unavailable | Worker logs, Docker Linux mode, sandbox image, socket permissions and cgroup support |
| Network failure after submitting | Retry without editing: the workspace reuses its request ID |
| Draft storage unavailable | Storage is blocked/full; copy code before closing the tab |
| Login fails behind proxy | HTTPS, cookie settings and exact allowed origin |
| Setup appears unexpectedly | Verify Compose project name and volume before creating accounts |

Python 3 is the only execution language; scoring is ICPC. SQLite and one worker target a local installation; measure capacity on actual hardware. The worker Docker socket is an administrative boundary and containers share the host kernel. A public service needs dedicated judging infrastructure and security review. SSO/LMS integration, multiple institutions and distributed workers remain future work: see the [roadmap](docs/ROADMAP.md).
