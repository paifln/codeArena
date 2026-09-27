# Contest platform audit and implementation plan

The existing application is React/TypeScript/Vite with TanStack Query, Zustand,
local Monaco, i18next (ru/kk/en), CSS tokens and light/dark themes. FastAPI routes
call synchronous SQLAlchemy services on SQLite WAL. Authentication uses rotating
cookie JWTs, SQLite revocation, CSRF and role/ownership dependencies.

Existing domain: User, Group, Problem/TestCase, Contest/ContestProblem,
Team/TeamMember, Submission/result/history, Clarification, Announcement, AuditLog.
One worker leases durable submissions and runs Python/C++/Java inside disposable
Docker containers with bounded consumer threads. A separate service verifies
SQLite backups. WebSocket contest invalidations supplement REST polling.

Already implemented: ICPC/shared ranks, independent scoring modes, fixed teams,
practice, freeze/unfreeze, ownership checks, clarifications/public answers,
announcements, single-submission rejudge, validated ZIP packages, judge health,
student presence heartbeat and operations dashboard. These will be extended.

## Implementation sequence

1. Add backward-compatible schema fields for contest rules/display, team metadata,
   clarification status, scoped audit events, durable rejudge batches, presence and
   deduplicated physical puzzle delivery records.
2. Centralize public/frozen/historical scoreboard projections. Add first solve,
   replay snapshots and persisted incremental reveal. Public displays require an
   explicit organizer opt-in and never expose private submissions or source.
3. Extend the existing judge transaction with timeline/reward reconciliation and
   rejudge audit. Derive monitor metrics from the real single-process/thread-slot
   architecture. Preserve immutable results for replay; never rerun judge for it.
4. Build a control center using existing contest actions, scoreboard, submissions
   and clarification components; improve explorer/statistics and team preparation.
5. Replace the existing creation form with a seven-step wizard using the same
   contest endpoint; include ordered problems, rules, freeze and language choices.
6. Add mobile puzzle delivery, collection/logo display, projector scoreboard and
   replay/reveal controls, and a LAN address/QR card. Keep existing visual tokens.
7. Test permissions, freeze non-disclosure, reward deduplication/rejudge, replay,
   migration preservation and UI flows. Build, back up, migrate and verify runtime.

No courses, lessons, homework, cloud API, new message broker or duplicate event
bus. AuditLog is the persisted contest timeline; WebSockets remain invalidation
hints. ZIP support remains an adapter around the current Problem model.
