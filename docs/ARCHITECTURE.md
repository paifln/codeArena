# Architecture

## Boundaries

- `backend/app/routes/`: HTTP input, authorization entry points and response handling.
- `backend/app/services/access.py`: contest visibility, ownership and participants.
- `backend/app/services/execution.py`: execution policy shared by REST, WebSocket and queue admission.
- `backend/app/services/submission_queue.py`: transactional admission, deduplication, limits and problem snapshots.
- `backend/app/services/serializers.py`: audience-specific representations and hidden-test filtering.
- `backend/app/services/scoreboard.py`: ICPC/partial-credit ranking, shared places, team aggregation and freeze visibility.
- `backend/app/services/judge_health.py`: heartbeat freshness and judge availability.
- `backend/judge/`: leasing, recovery, comparison and isolated execution.
- `frontend/src/features/solver/`: student workspace, execution notices, drafts and submission lifecycle.
- `frontend/src/components/`: shared timer and submission feedback.
- `frontend/src/lib/queryClient.ts`: server-state cache and account-boundary cleanup.

These are application modules, not separate microservices. Keep admission transactions inside services and HTTP details in routes. The service package reexports existing helpers to preserve callers during the split.

## Submission lifecycle

1. The editor reads `execution.allowed` and its reason. WebSocket notifications invalidate REST data; periodic REST refresh continues if notifications disconnect.
2. Non-empty source enables actions only while contest and judge permit execution. The API rechecks policy inside admission; client checks never grant access.
3. The editor sends a UUID `request_id`. An in-flight guard prevents double clicks. Failed responses retain the ID for retrying the same payload within that workspace session.
4. A SQLite write transaction serializes admission. A unique `(user_id, request_id)` index prevents duplicate rows. Matching retries return the original submission, including after contest finish; conflicting content returns 409. Access is still checked.
5. Admission checks problem membership, queue limits and throttling, then stores source plus a snapshot of tests and limits. Run uses samples or custom input; Submit uses all tests.
6. One worker acquires a lease, executes in disposable containers and writes results only while it owns the lease. Infrastructure errors do not count as wrong answers.
7. Student responses exclude hidden diagnostics; teacher access remains scoped to ownership/administrator permissions.

Request IDs are optional for compatibility. A full browser reload does not recover the previous request ID; submission history is the recovery path. HTTP timeout does not cancel already admitted work.

## State ownership

Contest state and worker health belong to the server. Drafts belong to the browser and are keyed by account, contest and problem. Keyed workspaces flush the latest draft before navigation; storage errors are visible. Drafts are not backed up to the server or encrypted on shared devices.

Private query data is cleared when the signed-in account changes. HTTP-only session cookies, CSRF validation and server permissions remain the security boundary.

Alembic owns persistent schema changes. Migration `0002` adds nullable request IDs and a unique index without rewriting existing submissions. Do not substitute `create_all()` for migrations outside tests.

## Deployment and verification

Use one API process, one worker process with 1-4 judging threads (default 2), a backup scheduler and the shared SQLite WAL volume. Do not scale Compose replicas. Only the worker mounts the Docker socket. Fonts and editor resources are served locally after build.

This deployment remains one API and one worker on SQLite WAL. Larger deployments need a separate design and measured quotas; changing the queue alone does not provide tenant isolation.

Python tests exercise HTTP permissions, migrations, domain behavior and optional real Docker execution. Vitest exercises browser state with mocked editor/transport. Releases still need real-browser checks with Monaco, keyboard navigation and the intended network/proxy setup.


## Version 3.1 boundaries

Migration 0003 adds contest mode/scoring/practice settings, teams and fixed rosters,
submission team snapshots/practice flags/points/feedback, editorials and test weights.
Native column additions preserve submission test results; a migration test verifies
existing history survives an upgrade.

Team membership controls shared-submission access; the submitting user is retained.
Official standings aggregate by captured team ID. Practice has a separate admission
policy and is excluded from standings and official dashboard metrics. Editorials
are absent from student responses until finish. Weighted snapshots are immutable;
the engine calculates points and standings select the best official score.

PythonRunner and CompiledRunner share the sandbox boundary. C++/Java compile once
inside a container; bounded archives pass through the worker as opaque data and
are unpacked only in fresh test containers. The API never gains execution privileges.
The editor separates local drafts by language.

app.operations owns backup, restore checks and rotation. Its service has no Docker
socket. The admin operations endpoint reports queue/heartbeat/errors/disk/backup
status without exposing source. See PERFORMANCE.md for the measured baseline.

Migration 0004 separates educational scoring from individual/team participation,
adds refresh-token revocation records and invalidates obsolete opaque sessions.
config.py validates deployment settings; middleware/ owns rate limiting and JSON
events. JWT session families remain checked in SQLite on every authenticated
request so password resets take effect immediately. See SECURITY.md for exact
policies and compatibility notes.

## Version 3.2 contest operations

Migration 0005 adds contest display/rule settings, scoped audit events, presence,
unique puzzle rewards and durable rejudge batches. Existing tables are extended
without rebuilding the submission parent table. No second event bus is introduced:
the worker records judgement and reward events in the same transaction as the verdict.

`services/scoreboard.py` owns live, public, frozen and historical projections.
Public HTTP and WebSocket routes use that projection; they cannot read the jury
reward ledger. Revealed submission IDs persist on the contest. Rejudge history
keeps the previous result visible while a job is pending and allows replay without
execution. Replay fidelity is limited by retained timestamps/history.

`services/contest_events.py` reconciles one reward per identity/problem and retains
delivery history when a solve is revoked. The existing worker heartbeat performs
idempotent legacy reward initialization, presence expiry, lifecycle events and
batch admission. Presence means a contest page heartbeat within 60 seconds,
not proof that a participant is physically present.

`services/rejudging.py` feeds durable batches into the existing capacity-limited
queue. `services/control_center.py` assembles organizer statistics. Slots represent
threads in the one worker process; there is no distributed worker scheduler.
`services/problem_packages.py` is the validated JSON ZIP adapter boundary for
future formats. Uploaded final images are decoded and re-encoded with bounded size.

React features under `features/contest/` share the scoreboard, wizard and display
components. Existing authenticated WebSockets invalidate query caches; public
WebSockets expose only a visible-standings revision. HTTP polling is a fallback.
Public display is opt-in; mobile delivery retains organizer/admin permissions.
The SQLite/single-API/single-worker deployment boundary remains unchanged.

## Version 3.4 participation and workflow

Migration 0007 stores completion by contest and participant/team identity. Queue
admission and completion use the same SQLite write serialization: a completion
cannot race a new submission. Outstanding checks prevent completion. An organizer
can reopen participation while the contest is running or paused. Completion is
independent of scoring, freeze and post-contest practice.

Private progress is computed from that identity's official submissions and is never
used as the public scoreboard. WebSocket snapshots include completion state to
invalidate teammates' views. Team members also share their private clarifications.
The reusable participation panel appears in the contest and solver; the problem
editor and list hook are extracted from the general pages module.

The organizer's main flow enters the control center directly. Infrastructure slot
counts and raw event identifiers are not shown in the event UI. Operational backup
and availability controls remain administrator-only. Production source maps are
disabled; browser-delivered JavaScript remains inspectable by design. Backend source,
credentials and hidden tests are not served as static files.
