# CodeArena

A self-hosted programming contest and teaching platform for schools and universities. Students write Python, C++ or Java in the browser; a separate Docker judge evaluates solutions.

**Version 3.1** adds teams, educational contests, ICPC tie handling, partial credit, practice, editorials, teacher feedback, operations monitoring and verified automatic backups.

## Features

- Administrator, teacher and student roles; groups, bulk accounts, scoped password resets and student removal.
- Individual or team participation (1–3 students per team), with a fixed team roster.
- ICPC, educational ICPC without penalties, or weighted partial-credit scoring, independently of participation mode.
- Python 3.12, C++20 (GCC 12) and Java 17, compiled and executed only inside disposable containers.
- Monaco editor, drafts separated by account/problem/language, sample runs and custom input.
- Scheduling, pause/resume, scoreboard freeze, clarifications and announcements.
- Practice after finish excluded from official results, post-contest editorials and teacher feedback.
- Russian, Kazakh and English, light/dark themes, locally bundled assets and a top-right profile menu.
- Durable queue, bounded parallel judging, lease recovery and retry deduplication.
- Operations dashboard and scheduled SQLite backups with restore verification.

## Quick start

Install Docker Engine with Compose v2, or Docker Desktop in **Linux containers** mode. From the repository root:

```sh
python tools/init_env.py
docker compose up --build -d
docker compose ps
```

Open **http://localhost:8000** and create the first administrator. No default credentials exist. Setup closes after the first account. After initializing `.env`, alternatively use `start.bat` or `sh start.sh`. The initialization helper uses only Python's standard library, creates a random 64-byte signing key, and never prints or replaces an existing key. Without Python on the host, copy `.env.example` to `.env` and set `SECRET_KEY` using your institution's cryptographic secret generator (128 hexadecimal characters).

The first build downloads dependencies and compilers. Once built, classroom operation does not require a CDN or cloud API. On Linux set `DOCKER_GID` to the group returned by `stat -c %g /var/run/docker.sock`; create `backups/` and grant UID 10001 write access.

## Classroom workflow

1. Administrators create teachers in Settings. Teachers create groups and students in Groups and distribute individual credentials privately.
2. Create problems with sample/hidden tests. Test weights default to 1; 0 excludes a test from partial points. Optionally write a Markdown editorial.
3. Create a contest, choose participation/scoring and assign groups or named teams. Team rosters are fixed at creation. Optionally enable practice after finish.
4. Start immediately or wait for the scheduled time. Students sign in at the same address with their own accounts.
5. **Run** checks samples/custom input; **Submit** checks all tests. Teachers can inspect, comment and rejudge.
6. After finish, students can read editorials and practice if enabled. Practice never changes official standings.

Use `http://<server-LAN-IP>:8000` from classroom devices. Their localhost is not the server. Use HTTPS for institutional deployment.

In Groups, administrators and the owning teacher can reset passwords, delete groups and remove students. Group deletion preserves accounts. Student removal revokes sessions/memberships, retains submission history and reserves the username. Password reset ends current student sessions. Sign out through the top-right profile menu.

## Scoring

| Mode | Ranking |
| --- | --- |
| Individual/team ICPC | Most solved, least total time, earliest last accepted submission; equal results share rank |
| Individual/team educational ICPC | Most solved; no time/rejection penalties; equal results share rank |
| Partial credit | Best percentage per problem, summed; equal points share rank |

A solved ICPC problem contributes elapsed whole minutes at first acceptance plus 20 minutes per earlier penalized rejection. Compilation errors, system errors, Run, practice and attempts after acceptance do not add penalties. Unsolved problems add no time. Pauses are excluded. Cells display the time/penalty breakdown.

Partial credit is **100 × passed test weight / total test weight**. All eligible tests run unless infrastructure limits fail. System errors yield no points. This is weighted per-test scoring, not dependency-based IOI subtasks. Ranking follows the [World Finals scoring rules](https://wf.icpc.global/2026/about/); this is not an officially certified ICPC system.

## Languages

| Selector | Toolchain | Convention |
| --- | --- | --- |
| Python 3.12 | CPython 3.12 | main.py |
| C++20 | GCC 12, -std=c++20 -O2 | main.cpp |
| Java 17 | OpenJDK 17, --release 17 | Main.java, public class Main |

Versions are provided by the sandbox image. C++/Java compile once per judgement; bounded artifacts travel to fresh test containers and never execute on the host. Compiler budget: 10 seconds / 512 MB. Java JVM overhead counts toward memory limits; use at least 128 MB for normal Java tasks. See [judge operation](backend/judge/README.md).

## Configuration and operation

Generate `.env` as above; it is excluded from Git. Never commit a signing key.

| Variable | Default / purpose |
| --- | --- |
| SECRET_KEY | Required random 64-byte hex signing key; no default |
| BIND_HOST, PORT | 0.0.0.0, 8000 |
| COOKIE_SECURE | false for HTTP development; true with HTTPS |
| ALLOWED_ORIGINS | Optional comma-separated exact browser origins |
| DOCKER_GID | Docker socket access group |
| RUN_COOLDOWN_SECONDS, SUBMIT_COOLDOWN_SECONDS | 2 / 5 seconds per user |
| MAX_QUEUE_SIZE | 200 pending jobs |
| JUDGE_CONCURRENCY | 2 slots within one worker; range 1–4 |
| BACKUP_INTERVAL_SECONDS | 21600 (six hours), minimum 60 |
| BACKUP_KEEP | 28 scheduler-generated copies |

One API process and one worker process share SQLite WAL. Do not scale Compose replicas. Each judging slot consumes CPU/memory; measure before increasing concurrency. Only the worker has Docker socket access. A TLS reverse proxy must forward WebSocket connections.

```sh
docker compose logs --tail=100 api worker backup
docker compose stop
docker compose up -d
```

The sandbox-image service exits after preparing the image. Backup runs continuously. Keep the same Compose project name and data volume when upgrading. Database: `/data/codearena-v3.db` in `arena-data`.

### Optional demo

```sh
docker compose exec api python -m app.demo --author-id 1
```

Use an existing administrator/teacher ID. This idempotently creates one draft demo and no accounts. Review assignments before starting it.

## Backups and upgrades

The backup service writes to host `./backups/`. Each copy is restored into a temporary database and checked for integrity, foreign keys and core row counts. Rotation touches only scheduler-generated files. System operations shows freshness, size, failures and an administrator-only download. The API mounts this directory read-only.

```sh
docker compose run --rm --no-deps backup python -m app.operations --once
docker compose run --rm --no-deps backup python -m app.operations --verify /backups/<backup-file>.db
```

Local copies share the host failure domain. Copy them to separate institutional storage and restrict access. Restore verification uses a 256 MB tmpfs by default; enlarge it for larger databases. See [operations](docs/OPERATIONS.md) before restoring live data.

After taking a verified backup:

```sh
docker compose stop
docker compose build
docker compose run --rm --no-deps api python -m app.migrate
docker compose up -d
```

Migration 0003 preserves accounts, submissions and test results. Existing contests default to individual ICPC with practice disabled. Pre-Alembic databases require a separate converter.

## Development and tests

Python 3.12+ and Node.js 22+, from the root:

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

From backend/: run `python -m app.migrate`, then `uvicorn app.main:app --host 127.0.0.1 --port 8000`. From frontend/: run `npm run dev`. Start `python -m judge.worker` separately with the same DATABASE_URL and a built sandbox image.

Real Docker checks, from the root:

```powershell
docker build -f Dockerfile.sandbox -t codearena-sandbox:local .
$env:PYTHONPATH='backend'
$env:RUN_SANDBOX_TESTS='1'
python -m pytest tests -q
```

Linux: `PYTHONPATH=backend RUN_SANDBOX_TESTS=1 python -m pytest tests -q`.

Isolated classroom baseline:

```sh
python tools/classroom_load.py --students 30 --output reports/classroom-load.json
```

This uses a temporary database, concurrent API handlers and real Docker judging. It measures admission/queue/verdict latency and verifies restoration. HTTP uses TestClient: network, TLS and browser rendering are not measured. Results depend on hardware/workload. See [performance notes](docs/PERFORMANCE.md).

Tests cover scoring/ties, team boundaries, practice isolation, editorial release, feedback permissions, all three languages, sandbox constraints, lease recovery and migration data preservation. Real-browser/accessibility review remains a release requirement.

## Architecture and scope

```text
Browser -> FastAPI routes -> policy/services -> SQLite WAL
                                              |       |
                                    bounded judge   backup scheduler
                                         |              |
                                Docker sandboxes    verified copies
```

See [architecture](docs/ARCHITECTURE.md), [security policies](docs/SECURITY.md) and [institutional roadmap](docs/ROADMAP.md). Future priorities include SSO/LMS, off-host backup automation, accessibility review and richer assignments. This deployment remains SQLite-only with one API and one worker.

Containers share the host kernel; the Docker socket is an administrative boundary. Public multi-tenant operation needs dedicated judging infrastructure and independent security review. This release does not claim multi-institution isolation or high availability.
