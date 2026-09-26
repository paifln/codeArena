# Architecture

## Boundaries

- `backend/app/routes/`: HTTP input, authorization entry points and response handling.
- `backend/app/services/access.py`: contest visibility, ownership and participants.
- `backend/app/services/execution.py`: execution policy shared by REST, WebSocket and queue admission.
- `backend/app/services/submission_queue.py`: transactional admission, deduplication, limits and problem snapshots.
- `backend/app/services/serializers.py`: audience-specific representations and hidden-test filtering.
- `backend/app/services/scoreboard.py`: ICPC standings and freeze visibility.
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

Use one API process, one worker and the shared SQLite WAL volume. Do not scale Compose replicas. Only the worker mounts the Docker socket. Fonts and editor resources are served locally after build.

Larger deployments need explicit distributed leasing, PostgreSQL migration, job delivery, per-institution authorization, observability and measured quotas. Replacing the queue alone does not provide tenant isolation.

Python tests exercise HTTP permissions, migrations, domain behavior and optional real Docker execution. Vitest exercises browser state with mocked editor/transport. Releases still need real-browser checks with Monaco, keyboard navigation and the intended network/proxy setup.
