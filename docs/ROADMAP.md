# School and university launch roadmap

This is proposed work, not a claim of current certification or production capacity. Begin with a supervised classroom pilot.

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

## P1: routine teaching

- Invitation/account recovery flows, password change on first login, validated roster import and offboarding. Add a visible clear-drafts action for shared devices.
- Courses/terms, reusable assignments, practice mode outside contests, deadlines, grading exports and teacher feedback.
- Metrics and alerts: queue depth/age, worker heartbeat, infrastructure errors, disk space and backup age. Avoid logging passwords or source.
- Automated encrypted off-host backups and scheduled restoration checks with an accountable operator.
- Institutional SSO and LMS integration. Evaluate [LTI 1.3 / LTI Advantage](https://www.imsglobal.org/lti-advantage-overview) for assignment launch and membership/grade exchange; prototype with the actual institutional LMS.
- Real-browser regression tests with Monaco, multiple accounts, expired sessions, teacher resume and unreliable networks.

## P2: expand after measured demand

- PostgreSQL and multiple isolated workers with explicit leases, quotas, retry budgets and load tests.
- Institution/course ownership enforced throughout queries and exports before multi-institution hosting.
- C++/Java/JavaScript through versioned sandbox images and language-specific resource/compilation tests.
- Partial-credit scoring and subtasks alongside agreed grading rules and regression tests.
- Code-similarity reports as teacher review aids, with evidence and student appeals; no automatic similarity penalties.

## Release gate

Record build/version, configuration, tests, browser/accessibility review, expected concurrency, measured limits, restore rehearsal and responsible operator. Agree on support arrangements with teachers. Passing unit tests alone does not demonstrate readiness for a high-stakes exam.
