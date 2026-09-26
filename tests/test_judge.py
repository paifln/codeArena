import pytest
from judge.comparators import equivalent
from judge.engine import judge
from judge.limits import Limits
from judge.sandbox import DockerSandbox, Execution


class FakeSandbox:
    def __init__(self, verdict='ACCEPTED', output='3\n'):
        self.verdict, self.output, self.inputs = verdict, output, []

    def available(self):
        return True, 'test double'

    def run(self, source, stdin, limits, *, compile_only=False):
        if compile_only:
            return Execution()
        self.inputs.append(stdin)
        return Execution(self.verdict, self.output)


SNAPSHOT = {'tests': [{'input_data': '1 2', 'expected': '3', 'is_sample': True},
                      {'input_data': 'hidden', 'expected': '3', 'is_sample': False}],
            'time_limit': 1, 'mem_limit': 64}


def test_comparator_preserves_significant_whitespace():
    assert equivalent('a  \r\nb\t\r\n\r\n', 'a\nb')
    assert not equivalent(' a', 'a')
    assert not equivalent('a  b', 'a b')
    assert not equivalent('a\n\nb', 'a\nb')


def test_run_never_executes_hidden_tests():
    sandbox = FakeSandbox()
    result = judge('source', 'python3', SNAPSHOT, kind='RUN', sandbox=sandbox)
    assert result.verdict == 'ACCEPTED'
    assert sandbox.inputs == ['1 2']


def test_custom_run_is_not_compared():
    sandbox = FakeSandbox(output='anything')
    result = judge('source', 'python3', SNAPSHOT, kind='RUN', custom_input='custom', sandbox=sandbox)
    assert result.verdict == 'ACCEPTED'
    assert sandbox.inputs == ['custom']


@pytest.mark.parametrize('verdict', ['TIME_LIMIT_EXCEEDED', 'MEMORY_LIMIT_EXCEEDED',
                                   'RUNTIME_ERROR', 'OUTPUT_LIMIT_EXCEEDED'])
def test_fail_fast_and_preserve_verdict(verdict):
    sandbox = FakeSandbox(verdict=verdict)
    result = judge('source', 'python3', SNAPSHOT, sandbox=sandbox)
    assert result.verdict == verdict
    assert len(result.tests) == 1


def test_wrong_answer_and_compile_error():
    assert judge('', 'python3', SNAPSHOT, sandbox=FakeSandbox(output='4')).verdict == 'WRONG_ANSWER'
    class CompileFailure(FakeSandbox):
        def run(self, *args, **kwargs):
            return Execution('COMPILATION_ERROR', stderr='bad syntax')
    assert judge('', 'python3', SNAPSHOT, sandbox=CompileFailure()).verdict == 'COMPILATION_ERROR'


def test_fail_closed_when_runtime_missing():
    class Unavailable(FakeSandbox):
        def available(self):
            return False, 'unavailable'
        def run(self, *args, **kwargs):
            raise AssertionError('must not execute')
    assert judge('', 'python3', SNAPSHOT, sandbox=Unavailable()).verdict == 'SYSTEM_ERROR'


def test_docker_configuration_has_no_host_mounts_or_privileges():
    args = DockerSandbox().create_args('test', Limits())
    for flag, value in [('--network', 'none'), ('--user', '10001:10001'), ('--cap-drop', 'ALL'),
                        ('--security-opt', 'no-new-privileges:true'), ('--pids-limit', '16')]:
        assert args[args.index(flag) + 1] == value
    assert '--read-only' in args
    assert not any(flag in args for flag in ['--privileged', '-v', '--volume', '--mount', '--env', '-e'])


@pytest.mark.parametrize('missing', ['MemoryLimit', 'SwapLimit', 'PidsLimit', 'CpuCfsQuota', 'CpuCfsPeriod'])
def test_docker_fails_closed_without_enforced_resource_limits(monkeypatch, missing):
    import json
    from subprocess import CompletedProcess
    runtime = DockerSandbox()
    capabilities = {'OSType': 'linux', 'SecurityOptions': ['name=seccomp,profile=builtin'],
                    'MemoryLimit': True, 'SwapLimit': True, 'PidsLimit': True,
                    'CpuCfsQuota': True, 'CpuCfsPeriod': True}
    capabilities[missing] = False
    def command(*args, **kwargs):
        assert args[0] == 'info', 'must reject before inspecting an image'
        return CompletedProcess(args, 0, json.dumps(capabilities).encode(), b'')
    monkeypatch.setattr(runtime, '_command', command)
    ready, detail = runtime.available()
    assert not ready and 'cgroup' in detail


def test_docker_accepts_enforced_resource_limits(monkeypatch):
    import json
    from subprocess import CompletedProcess
    runtime = DockerSandbox()
    capabilities = {'OSType': 'linux', 'SecurityOptions': ['name=seccomp,profile=builtin'],
                    'MemoryLimit': True, 'SwapLimit': True, 'PidsLimit': True,
                    'CpuCfsQuota': True, 'CpuCfsPeriod': True}
    monkeypatch.setattr(runtime, '_command', lambda *args, **kwargs: CompletedProcess(
        args, 0, json.dumps(capabilities).encode() if args[0]=='info' else b'[]', b''))
    assert runtime.available()[0]


@pytest.fixture
def queue_db(tmp_path):
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from app.db import Base
    from app.models import Submission
    engine = create_engine(f'sqlite:///{tmp_path / "queue.db"}')
    Base.metadata.create_all(engine)
    factory = sessionmaker(engine, expire_on_commit=False)
    with factory() as db:
        # Queue tests isolate lease mechanics; application tests cover foreign keys.
        db.add(Submission(user_id=1, contest_id=1, problem_id=1, source='print(3)',
                          language='python3', kind='SUBMIT', problem_snapshot=SNAPSHOT))
        db.commit()
    yield factory
    engine.dispose()


def test_atomic_claim_and_idempotent_persistence(queue_db):
    from judge.worker import claim, persist
    from judge.engine import Judgement
    from app.models import Submission
    job = claim(queue_db)
    assert job is not None
    assert claim(queue_db) is None
    assert persist(queue_db, job, Judgement('ACCEPTED'))
    assert not persist(queue_db, job, Judgement('WRONG_ANSWER'))
    with queue_db() as db:
        assert db.get(Submission, job['id']).status == 'ACCEPTED'


def test_recovery_invalidates_old_worker_and_bounds_retries(queue_db):
    import time
    from judge.worker import claim, persist, recover_stale
    from judge.engine import Judgement
    from judge.limits import LEASE_SECONDS
    from app.models import Submission
    old_job = claim(queue_db)
    assert recover_stale(queue_db, time.time() + LEASE_SECONDS + 1) == 1
    new_job = claim(queue_db)
    assert new_job['lease_token'] != old_job['lease_token']
    assert not persist(queue_db, old_job, Judgement('ACCEPTED'))
    assert recover_stale(queue_db, time.time() + LEASE_SECONDS + 1) == 1
    assert claim(queue_db) is not None
    assert recover_stale(queue_db, time.time() + LEASE_SECONDS + 1) == 1
    assert claim(queue_db) is None
    with queue_db() as db:
        assert db.get(Submission, old_job['id']).status == 'SYSTEM_ERROR'


def test_concurrent_workers_only_one_claims(queue_db):
    from concurrent.futures import ThreadPoolExecutor
    from judge.worker import claim
    with ThreadPoolExecutor(max_workers=4) as pool:
        jobs = list(pool.map(lambda _: claim(queue_db), range(4)))
    assert sum(job is not None for job in jobs) == 1


def test_concurrent_initial_heartbeat_is_atomic(queue_db):
    from concurrent.futures import ThreadPoolExecutor
    from judge.worker import heartbeat
    from app.models import SystemSetting
    with ThreadPoolExecutor(max_workers=4) as pool:
        list(pool.map(lambda _: heartbeat(queue_db, True, 'ready'), range(8)))
    with queue_db() as db:
        record = db.get(SystemSetting, 'judge_heartbeat')
        assert record.value['available'] is True
