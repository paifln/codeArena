# Classroom baseline

The checked-in [measurement](../reports/classroom-load.json) is a synthetic
30-student burst on the development Windows/Docker Desktop host. Each student
submits one Python sum solution with two tests. Two judging slots run in one
worker process against a temporary SQLite WAL database.

- Accepted: 30/30; admission/result failures: 0.
- p95 admission latency: 0.924 seconds.
- p95 queue wait: 49.913 seconds.
- p95 end-to-end verdict latency: 54.871 seconds.
- Run duration, including restore verification: 55.52 seconds.
- Backup restoration verified successfully.

These figures are a reproducible baseline, not a promise for a school server.
HTTP uses FastAPI TestClient in process. It excludes TCP, TLS, browser/Monaco
rendering, authentication setup and classroom Wi-Fi. Other host workloads can
affect results. It is one burst, not a sustained-load or maximum-capacity test.

The queue wait shows why admission speed alone is insufficient. For a class
that requires faster verdicts, benchmark a dedicated Linux judge host and tune
JUDGE_CONCURRENCY (1–4). Each slot may use one CPU and up to 512 MB during
compilation, plus container/runtime overhead. Keep one worker process for this
SQLite deployment; do not increase Compose replica count.

## Reproduce

Build the sandbox, install backend development dependencies, then run:

```sh
python tools/classroom_load.py --students 30 --output reports/classroom-load.json
```

The command uses an isolated database and synthetic sessions, never real
student credentials. It exits unsuccessfully if any verdict is not accepted.
Run it on the intended deployment hardware, with its actual test suites and
languages, before setting service targets. Test sustained runs and real browser
sessions separately.

## Recovery coverage

The suite simulates an interrupted, expired worker lease, completes the job
with real Docker execution and rejects a stale worker's attempt to overwrite
the result. Backup tests restore a database and validate data. These are not a
physical host power-loss drill; the institution should rehearse host failure
and recovery from separate storage before a high-stakes assessment.
