"""Trusted sandbox entrypoint, installed in the isolated image only.

Do not import this module from the worker. It prepares one invocation and execs
the interpreter; all execution and compilation happens inside the container.
"""
import json
import os
import resource
import sys

payload = json.load(sys.stdin)
source = payload['source']
resource.setrlimit(resource.RLIMIT_FSIZE, (1024 * 1024, 1024 * 1024))
resource.setrlimit(resource.RLIMIT_NOFILE, (64, 64))
resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
if payload['mode'] == 'compile':
    try:
        compile(source, 'main.py', 'exec', dont_inherit=True)
    except (SyntaxError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        sys.exit(65)
    sys.exit(0)
with open('/tmp/main.py', 'w', encoding='utf-8') as stream:
    stream.write(source)
with open('/tmp/input.txt', 'w', encoding='utf-8') as stream:
    stream.write(payload['input'])
fd = os.open('/tmp/input.txt', os.O_RDONLY)
os.dup2(fd, 0)
os.close(fd)
os.chdir('/tmp')
os.execve(sys.executable, [sys.executable, '-I', '-B', '/tmp/main.py'],
          {'PATH': '/usr/local/bin:/usr/bin:/bin', 'LANG': 'C.UTF-8', 'HOME': '/tmp'})
