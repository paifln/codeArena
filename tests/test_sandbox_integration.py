"""Opt-in, real Docker tests. All submitted code executes INSIDE the sandbox.

RUN_SANDBOX_TESTS=1 PYTHONPATH=backend pytest tests/test_sandbox_integration.py
"""
import os
import pytest
from judge.limits import Limits
from judge.sandbox import DockerSandbox

pytestmark = pytest.mark.skipif(os.environ.get('RUN_SANDBOX_TESTS') != '1', reason='requires built Docker sandbox')


@pytest.fixture(scope='module')
def sandbox():
    runtime = DockerSandbox()
    ready, detail = runtime.available()
    assert ready, detail
    return runtime


@pytest.mark.parametrize(('source', 'expected'), [
    ('if __name__ == "__main__":\n print(sum(map(int,input().split())))', 'ACCEPTED'),
    ('raise ValueError("failure")', 'RUNTIME_ERROR'),
    ('while True: pass', 'TIME_LIMIT_EXCEEDED'),
    ('while True: print("x"*4096)', 'OUTPUT_LIMIT_EXCEEDED'),
    ('x = bytearray(512*1024*1024)', 'MEMORY_LIMIT_EXCEEDED'),
])
def test_verdicts(sandbox, source, expected):
    result = sandbox.run(source, '1 2\n', Limits(1, 64))
    assert result.verdict == expected, result
    if expected == 'ACCEPTED':
        assert result.stdout == '3\n'


def test_compile_stage_does_not_execute(sandbox):
    assert sandbox.run('while True: pass', '', Limits(), compile_only=True).verdict == 'ACCEPTED'
    assert sandbox.run('def :', '', Limits(), compile_only=True).verdict == 'COMPILATION_ERROR'


def test_network_filesystem_and_identity(sandbox):
    source = '''import os, socket
assert os.getuid() == 10001
assert not os.path.exists('/var/run/docker.sock')
assert not os.path.exists('/app')
assert not any('SECRET' in key or 'DATABASE' in key for key in os.environ)
try:
    open('/forbidden-write', 'w')
except OSError:
    pass
else:
    raise AssertionError('writable root')
sock = socket.socket()
sock.settimeout(.2)
try:
    sock.connect(('1.1.1.1', 53))
except OSError:
    pass
else:
    raise AssertionError('network access')
print('isolated')
'''
    result = sandbox.run(source, '', Limits(2, 64))
    assert result.verdict == 'ACCEPTED', result
    assert result.stdout == 'isolated\n'


def test_process_limit_is_enforced(sandbox):
    source = '''import os, time
children = []
try:
    for _ in range(32):
        pid = os.fork()
        if pid == 0:
            time.sleep(5)
            os._exit(0)
        children.append(pid)
except OSError:
    print('limited', flush=True)
finally:
    for pid in children:
        os.kill(pid, 9)
    for pid in children:
        os.waitpid(pid, 0)
'''
    result = sandbox.run(source, '', Limits(2, 64))
    assert result.verdict == 'ACCEPTED', result
    assert result.stdout == 'limited\n'
