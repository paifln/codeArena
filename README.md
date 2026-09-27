# CodeArena

A self-hosted programming contest platform for schools, universities and local competitions. Organizers manage an event from one control center; participants solve problems in a browser, track their progress and finish their participation explicitly.

**Version 3.4** focuses on everyday usability: participant completion, team-wide submission closure, teacher-controlled reopening, contest editing and archiving, and clearer organizer screens. The interface supports English, Russian and Kazakh, with light and dark themes.

## Start locally

Install Docker Desktop in **Linux containers** mode (or Docker Engine with Compose v2). Run from the repository root:

```sh
python tools/init_env.py
docker compose up --build -d
```

Open **http://localhost:8000** and create the first administrator. There are no default accounts or passwords. The initialization helper creates `.env` with a random signing key and preserves an existing configuration. Alternatively, initialize `.env` and use `start.bat` or `sh start.sh`.

The first build needs internet access to download dependencies. Once built, local contests use bundled assets and do not require a CDN. External problem import requires internet access on the server.

To stop:

```sh
docker compose stop
```

Stopping containers preserves data. Do not remove the `arena-data` volume.

## Connect classroom computers

Keep the server computer running. On another computer in the same network, open `http://<server-LAN-IP>:8000`. The control center provides the address and a QR code; use `CODEARENA_LAN_HOST` in `.env` if automatic detection chooses the wrong adapter.

Allow inbound TCP traffic to the configured port on the server. Guest Wi-Fi/client isolation may prevent classroom devices from reaching it. Each student signs in with an account created by the organizer. Use HTTPS for institutional deployment.

## For organizers

1. Create teachers in **Settings**, then groups and student accounts in **Groups**. Password reset and account removal respect ownership permissions.
2. Add problems with sample and hidden tests. PDF/DOCX attachments can be selected during creation or managed later. Import public statements from Codeforces, AtCoder or CSES and review them before use.
3. Create a contest with the setup wizard: schedule, ordered problems, individual participants or teams, scoring, languages and rules.
4. Open the contest's **Control center** to start, pause, extend or finish the event. Manage submissions, questions, standings, announcements and puzzle delivery there.
5. The **Teams** tab shows who has finished. Use **Reopen participation** to let a participant or team continue while the contest is running or paused.
6. Edit the title, description and rules in **Settings**. Scheduling changes are available before the start. Archive finished contests to hide them from participants while retaining their results; restore them from the archive tab.

Team CSV import accepts `team_name,organization,member1,member2,member3`. It creates an individual account for each member and provides credentials once for download. Save these privately. Team members share official submissions and standings; cancelling the wizard does not remove already provisioned accounts.

## For participants

1. Sign in and open an assigned contest.
2. Read the rules, statement and attachments. Choose an allowed language and write a solution. Drafts are saved locally per account, problem and language.
3. **Run** checks examples or custom input. **Submit** checks the official test set. Running a program never adds a scoreboard penalty.
4. Follow the progress panel and per-problem verdicts. Continue to the next unsolved problem, review submissions or ask a clarification.
5. Select **Finish participation** when done. Wait for any pending checks and confirm the action. For a team, this closes official runs/submissions for every member. Submitted solutions and results remain saved; unsubmitted editor text is not a submission.

A teacher can reopen participation before the contest ends. Completion does not change score, rank or penalties. Post-contest practice, when enabled, stays separate from official results.

## Contest features

- Individual and team contests with fixed rosters of one to three members.
- ICPC scoring, educational scoring without time/rejection penalties, and weighted partial credit.
- Configurable penalties and allowed languages, scheduling, pause/resume, clarifications and announcements.
- Live standings, first solves, scheduled/manual freeze and sequential reveal.
- Opt-in public projector displays and historical replay without rerunning solutions.
- One puzzle reward per participant/team and problem, with delivery tracking and an optional final image.
- Single or bulk rejudging with retained judgement history.
- Verified database backups and administrator-only recovery downloads.

Public display is disabled by default. Frozen public standings and puzzle collections share the same visibility rules. Reveal is available after the contest and outstanding judging finish. Archiving disables public access. A rejudge may revise results; completion is a participation state, not a permanent guarantee of acceptance.

## Supported languages

| Language | Runtime | Source convention |
| --- | --- | --- |
| Python | CPython 3.12 | `main.py` |
| C++ | GCC 12, C++20 | `main.cpp` |
| Java | OpenJDK 17 | `Main.java`, `public class Main` |
| JavaScript | Node.js 18, CommonJS | `main.js` |
| Go | Go 1.19, CGO disabled | `main.go`, `package main` |
| C# | Mono 6.8 / mcs | `Main.cs`, static `Main` |

Choose allowed languages in the wizard or settings outside an active contest. All execution takes place in isolated containers. Package/module downloads are unavailable during execution; C# uses Mono, not modern .NET. See [judge operation](backend/judge/README.md) for limits.

## Important boundaries

- External imports include statements and examples, **not hidden tests**. Codeforces may block automatic fetching; a saved public HTML page can be supplied instead. Review formatting, limits and reuse permissions. JSON ZIP packages remain supported; Polygon/YAML packages and custom checkers are not implemented.
- Attachments are limited to three PDF/DOCX files of 5 MB each. Downloads require contest access. Files are not virus-scanned or converted. Upload/delete is locked during an active contest.
- Comment review highlights explicit assistant-related phrases for human review. It does not determine AI authorship or apply penalties; student code is not sent to an external AI service.
- Browser code cannot disconnect a student's computer from the internet. The optional [managed Windows network script](docs/CLASSROOM_NETWORK.md) requires local administrator access and has timed/manual restoration. No remote device agent is installed.
- Puzzle delivery currently requires the contest owner or an administrator. Replay depends on retained timestamps and judgement history; it cannot reconstruct missing historical events.

## Backups and upgrades

Backups are written to `./backups/` and checked by restoring a temporary copy. Store an additional copy outside the server. Keep `.env`, database files, credentials and backups out of Git.

```sh
docker compose run --rm --no-deps backup python -m app.operations --once
docker compose stop
docker compose build
docker compose run --rm --no-deps api python -m app.migrate
docker compose up -d
```

Migration 0007 adds participant completion without deleting existing accounts, contests or submissions. Preserve the signing key, Compose project name and data volume. See [operations and recovery](docs/OPERATIONS.md) before restoring data. Linux hosts need the Docker socket group configured with `DOCKER_GID` and a backup directory writable by UID 10001.

## Development and verification

Python 3.12+ and Node.js 22+:

```sh
python -m venv .venv
# Activate .venv for your shell.
pip install -r backend/requirements-dev.txt
python -m pytest tests -q
cd frontend
npm ci
npm test
npm run build
```

Real execution tests require the sandbox image and `RUN_SANDBOX_TESTS=1`. `python tools/browser_smoke.py` checks the interface with an isolated database, a built frontend and installed Microsoft Edge; install `playwright` first. It never modifies the live database.

Before an institutional event, rehearse student and organizer workflows, recovery, network restrictions and accessibility on the actual classroom hardware. See [deployment priorities](docs/ROADMAP.md), [security](docs/SECURITY.md) and [performance evidence](docs/PERFORMANCE.md). CodeArena is a local single-server deployment, not a claim of ICPC certification, high availability or unrestricted public multi-tenant hosting.
