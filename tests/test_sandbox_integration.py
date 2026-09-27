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


@pytest.mark.parametrize(('language','source'), [
 ('cpp20','#include <iostream>\nint main(){int a,b;std::cin>>a>>b;std::cout<<a+b<<"\\n";}'),
 ('java17','import java.util.*; public class Main {public static void main(String[] args){Scanner s=new Scanner(System.in);System.out.println(s.nextInt()+s.nextInt());}}'),
])
def test_compiled_languages(sandbox,language,source):
    from judge.engine import judge
    snapshot={'time_limit':2,'mem_limit':128,'tests':[{'input_data':'1 2','expected':'3','is_sample':True},{'input_data':'8 9','expected':'17','is_sample':False}]}
    result=judge(source,language,snapshot,sandbox=sandbox)
    assert result.verdict=='ACCEPTED',(result.error,result.tests)
    assert len(result.tests)==2
    broken=judge('this is not valid source',language,snapshot,sandbox=sandbox)
    assert broken.verdict=='COMPILATION_ERROR',broken


def test_interrupted_lease_recovers_with_real_execution(tmp_path, sandbox):
    import time
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from app.db import Base
    from app.models import Submission
    from judge.worker import claim, persist, run_once
    from judge.engine import Judgement
    from judge.limits import LEASE_SECONDS
    engine=create_engine(f'sqlite:///{tmp_path / "recovery.db"}')
    Base.metadata.create_all(engine);factory=sessionmaker(engine)
    with factory() as db:
        item=Submission(user_id=1,contest_id=1,problem_id=1,source='print(3)',language='python3',kind='SUBMIT',
            problem_snapshot={'tests':[{'input_data':'','expected':'3','is_sample':True}]})
        db.add(item);db.commit();sid=item.id
    interrupted=claim(factory)
    with factory() as db:
        db.get(Submission,sid).started_at=time.time()-LEASE_SECONDS-1;db.commit()
    assert run_once(factory,sandbox)
    assert not persist(factory,interrupted,Judgement('WRONG_ANSWER'))
    with factory() as db:
        assert db.get(Submission,sid).status=='ACCEPTED'
        assert db.get(Submission,sid).attempt_count==2
    engine.dispose()
