# Judge operation

The API only inserts durable `QUEUED` rows. A separate `python -m judge.worker`
process owns the SQLite queue. Conditional updates acquire a unique lease;
results are persisted only while the same lease still owns `RUNNING`. A lease
older than 300 seconds is queued again, at most three attempts before a
non-penalized `SYSTEM_ERROR`. A teacher can explicitly rejudge that result.
Run one worker process with JUDGE_CONCURRENCY set to 1-4 slots (default 2). The tests also verify that
concurrent claim attempts cannot both acquire the same submission.

Build `Dockerfile.sandbox` as `codearena-sandbox:local` (or set `SANDBOX_IMAGE`).
Only the worker needs the Docker CLI/socket. Never mount the socket on the API.
The worker checks that Docker is Linux, reports seccomp and working memory,
swap, PID and CPU cgroup limits, and that the image exists. Unsupported cgroups
(including incompletely configured rootless Docker) fail closed. No host
execution fallback exists. Availability is written to the
database every five seconds, including while a submission is being judged.

Each compile check and each test gets a fresh container with the Docker default
seccomp profile, all capabilities dropped, no-new-privileges, non-root UID,
no network, read-only root, 16 MiB noexec `/tmp`, 32 MiB executable `/work`,
16 processes (32 for Java), one CPU, bounded
memory with swap disabled, 64 file descriptors and 1 MiB file size limit.
There are no host mounts, inherited service environment variables or secrets.
The source and test input travel through stdin; no expected answers enter the
container. Python compilation checks syntax without executing source.
C++20 uses GCC 12; Java uses OpenJDK 17. Compilation has a 10-second/512-MB
budget. Bounded artifacts are passed as base64 ZIP data to fresh test containers
and never executed by the worker. Paths and expansion size are checked. Java JVM
overhead counts toward the memory limit. Compiler failures are non-penalized CE;
infrastructure errors remain SYSTEM_ERROR.
Execution uses normal Python `__main__` semantics. After each invocation the
worker force-removes the container. A background collector removes expired
containers left behind by a worker crash.

Stdout and stderr are independently capped at 256 KiB. Exceeding either produces
`OUTPUT_LIMIT_EXCEEDED`, a penalized verdict. CPU hard limits and a host wall
timer stop excessive execution; the wall limit includes a fixed one-second
Docker/bootstrap allowance. Reported `time_ms` is end-to-end container wall
time, not Python CPU time. Peak memory is currently unavailable (`memory_kb=0`),
while cgroup memory is enforced and an OOM kill maps to `MEMORY_LIMIT_EXCEEDED`.
Submission work has a 120-second total budget; exhausting the infrastructure
budget is `SYSTEM_ERROR` and must not penalize the student.

ICPC judging stops at the first failure; compilation errors are not penalized.
Partial credit checks all tests and computes weighted points. Practice never
changes official standings. Run uses only samples, or the supplied
custom input with no expected-output comparison. The comparator normalizes
CRLF/CR to LF, strips trailing spaces/tabs on each line and ignores final empty
lines. Leading whitespace, internal spaces and internal empty lines matter.
Hidden stdout/stderr must stay teacher-only: student code can echo test input.

Docker isolates workloads for a trusted LAN deployment, not arbitrary hostile
Internet tenants or kernel exploits. The Sandbox protocol permits replacing it
with a stronger runtime. Docker itself and its images must be kept updated.

Verification (from the repository root):

```powershell
$env:PYTHONPATH='backend'
python -m pytest tests/test_judge.py -q
docker build -f Dockerfile.sandbox -t codearena-sandbox:local .
$env:RUN_SANDBOX_TESTS='1'
python -m pytest tests/test_sandbox_integration.py -q
```

The opt-in integration tests execute all adversarial examples only in containers:
unbounded loop/output, excessive memory allocation, outbound network attempt,
root filesystem write, secret/socket presence and exceeding the PID limit.
