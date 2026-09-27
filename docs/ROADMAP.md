# School and university launch roadmap

Version 3.2 adds contest control, public displays, reveal/replay, puzzle rewards and bulk rejudging to the existing local contest platform. See PERFORMANCE.md for the 30-student baseline. Remaining work is listed below; this is not a certification or capacity claim.

## P0: before the first real assessment

| Work | Acceptance evidence |
| --- | --- |
| Rehearse student workflow | Teacher provisions class; students sign in, open assigned contests, Run and Submit; verify pause/resume and disconnection |
| Measure capacity | Simulate intended class size and simultaneous submissions on deployment hardware; record queue delay, p95 verdict time and failures |
| Prove recovery | Restart worker, interrupt network and restore backup on another installation; verify submissions and standings |
| Harden deployment | HTTPS, restricted admin access, maintained images, appropriate judge isolation and documented rollback |
| Review security | Independent review of auth, role boundaries, uploads, hidden tests and sandbox using applicable [OWASP ASVS requirements](https://owasp.org/projects/asvs) |
| Define data handling | Institution approves collected fields, retention/deletion, access to student code, backup retention and incident contacts |
| Review accessibility | Test editor and complete flows with keyboard, screen reader, zoom and contrast against [WCAG 2.2](https://www.w3.org/TR/WCAG22/) |

## P1: routine contests

- Invitation/account recovery flows, password change on first login, validated roster import and offboarding. Add a visible clear-drafts action for shared devices.
- Scoped volunteer accounts, printable puzzle delivery slips and wider validated problem-package compatibility.
- Extend existing operations monitoring with retained metrics, external alert delivery and service targets. Avoid logging passwords or source.
- Automated encrypted off-host backups and scheduled restoration checks with an accountable operator.
- Real-browser regression tests with Monaco, multiple accounts, expired sessions, teacher resume and unreliable networks.

## P2: expand after measured demand

- Repeat capacity tests and tune bounded slots/quotas within the single-worker SQLite deployment.
- Institution ownership enforced throughout queries and exports before multi-institution hosting.
- Additional runtime versions and JavaScript, with language-specific resource tests.
- Dependency-based subtasks beyond existing weighted per-test scoring.
- Code-similarity reports as teacher review aids, with evidence and student appeals; no automatic similarity penalties.

## Release gate

Record build/version, configuration, tests, browser/accessibility review, expected concurrency, measured limits, restore rehearsal and responsible operator. Agree on support arrangements with teachers. Passing unit tests alone does not demonstrate readiness for a high-stakes exam.
