# Security policies

## Authentication and migration

Access JWTs expire after 15 minutes; refresh JWTs and their session family expire after seven days. Both use HttpOnly, SameSite=Strict cookies; enable COOKIE_SECURE behind HTTPS. Tokens are never stored in localStorage. JWT verification fixes HS256, issuer, audience, required claims and token type. SECRET_KEY must contain 128 hexadecimal characters generated from 64 random bytes. Startup fails without it.

Refresh rotates tokens transactionally. SQLite retains revoked token IDs until expiry; reuse revokes the user's sessions. Password changes/resets revoke access sessions and refresh tokens immediately. The browser refreshes once on an authenticated request's 401 and retries that request; concurrent tabs coordinate through Web Locks where supported. Logout revokes the current session family.

Migration 0004 invalidates old opaque sessions, preserving users/passwords/results. Existing Argon2 hashes remain readable and are upgraded at successful login where compatible. New passwords use bcrypt cost 12 and must not exceed 72 UTF-8 bytes; long legacy passwords are never truncated. Back up before migration. A restored database can restore old session state: rotate SECRET_KEY after a disaster restore if session invalidation is required.

## HTTP and data boundaries

- SQLAlchemy uses bound parameters. Ownership/membership checks and role dependencies protect objects, submissions, administration and backup downloads.
- State changes require a CSRF header bound to the session. Supplied Origin must match this site or an explicitly allowed origin; cookies use SameSite=Strict.
- SlowAPI limits aggregate application traffic to 100 requests/minute/IP and authentication mutations to 5/minute/IP. Health probes are exempt. Login additionally has a persistent SQLite limit of 5 attempts/15 minutes/IP, including failed attempts.
- Do not expose a proxy that replaces every client address with one IP. Configure Uvicorn's trusted proxy addresses narrowly; never trust arbitrary forwarded headers. A NAT sharing one IP shares the quota.
- Streamed request bodies are limited to 10 MiB, independently of Content-Length. Source is capped at 64 KiB of UTF-8 in API and judge. Input models forbid extra fields and use strict typing; ISO datetimes and UUID strings have explicit JSON adapters.
- CSP, HSTS, X-Frame-Options, nosniff, Referrer-Policy and Permissions-Policy are applied, including rejected requests. CSP permits local Monaco workers/styles; raw Markdown HTML is not enabled. HSTS takes effect over HTTPS.
- No backend feature fetches user-supplied URLs. Bundled UI assets work offline after images are built; CDN-backed Swagger/ReDoc pages are disabled. OpenAPI JSON remains available.
- Archive import reads validated members in memory, never extracts them to the host. Backup filenames are restricted to generated numeric names, checked for traversal/symlinks and served only to administrators.

## Runtime and logs

Only the worker mounts the Docker socket. Services and sandboxes run as non-root with dropped capabilities; sandbox containers have no network, a read-only root, seccomp and bounded resources. Source is sent over stdin, never interpolated into shell commands. Do not scale API/worker replicas.

Application logs are JSON with allowlisted fields. Authentication actions, HTTP errors, queue admission/claim/recovery, judge verdicts and verified backups are recorded. Admission records a source hash, never source text. Request bodies, cookies, tokens and exception text are excluded. Database audit records remain separately available. Logs do not claim to be a tamper-proof audit ledger.

Backups contain password hashes and student source. Restrict host directory access and downloaded copies. The backup scheduler verifies restoration, integrity, foreign keys and core counts before rotation; keep off-host copies according to institutional retention requirements.

## Implementation notes

The existing synchronous SQLAlchemy unit-of-work is retained: FastAPI runs synchronous route handlers in its thread pool, and WebSocket database snapshots use asyncio.to_thread. This differs from the illustrative async database module in the supplied specification. Converting transaction boundaries to AsyncSession is a separate architecture change, not a security prerequisite. The existing routes/services and feature-based frontend directory layout is retained and documented in ARCHITECTURE.md.

Tests exercise token expiry/rotation/replay, reset revocation, role/object boundaries, limits, strict input, migrations, backups and real Docker execution. They do not replace independent security review or real-browser/network testing.

Implementation references: [PyJWT validation](https://pyjwt.readthedocs.io/en/latest/usage.html), [SlowAPI limits](https://slowapi.readthedocs.io/en/stable/api/), [Pydantic strict mode](https://docs.pydantic.dev/latest/concepts/strict_mode/).
