"""Trusted entrypoint. This file runs only inside a disposable sandbox container."""
import base64
import io
import json
import os
from pathlib import Path
import resource
import subprocess
import sys
import zipfile

payload = json.load(sys.stdin)
source = payload['source']
language = payload.get('language', 'python3')
resource.setrlimit(resource.RLIMIT_FSIZE, (1024 * 1024, 1024 * 1024))
resource.setrlimit(resource.RLIMIT_NOFILE, (64, 64))
resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
env = {'PATH': '/usr/local/bin:/usr/bin:/bin', 'LANG': 'C.UTF-8', 'HOME': '/tmp'}
os.chdir('/work')
if payload['mode'] == 'compile':
    if language == 'python3':
        try:
            compile(source, 'main.py', 'exec', dont_inherit=True)
        except (SyntaxError, ValueError) as exc:
            print(str(exc), file=sys.stderr)
            sys.exit(65)
        sys.exit(0)
    if language == 'cpp20':
        Path('main.cpp').write_text(source, encoding='utf-8')
        command = ['g++', '-std=c++20', '-O2', '-pipe', 'main.cpp', '-o', 'main']
    elif language == 'java17':
        Path('Main.java').write_text(source, encoding='utf-8')
        command = ['javac', '-J-Xmx256m', '-J-XX:+UseSerialGC', '--release', '17', '-encoding', 'UTF-8', '-d', '.', 'Main.java']
    else:
        sys.exit(65)
    code = subprocess.call(command, stdout=sys.stderr, stderr=sys.stderr, env=env)
    if code:
        sys.exit(65)
    files = [Path('main')] if language == 'cpp20' else list(Path('.').rglob('*.class'))
    if not files or sum(p.stat().st_size for p in files) > 1024*1024:
        print('Compiled artifact is missing or too large', file=sys.stderr)
        sys.exit(65)
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as archive:
        for path in files:
            archive.write(path, str(path))
    sys.stdout.write(base64.b64encode(buffer.getvalue()).decode('ascii'))
    sys.exit(0)
if language == 'python3':
    Path('/tmp/main.py').write_text(source, encoding='utf-8')
    command = [sys.executable, '-I', '-B', '/tmp/main.py']
else:
    with zipfile.ZipFile(io.BytesIO(base64.b64decode(payload['artifact'], validate=True))) as archive:
        entries = archive.infolist()
        if len(entries) > 256 or sum(i.file_size for i in entries) > 1024*1024:
            sys.exit(65)
        for entry in entries:
            target = Path(entry.filename)
            if target.is_absolute() or '..' in target.parts or '\\' in entry.filename:
                sys.exit(65)
            if language == 'cpp20' and entry.filename != 'main':
                sys.exit(65)
            if language == 'java17' and target.suffix != '.class':
                sys.exit(65)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(archive.read(entry))
    if language == 'cpp20':
        os.chmod('/work/main', 0o700)
        command = ['/work/main']
    else:
        heap = max(16, int(payload['memory_mb']) - 96)
        command = ['java', '-XX:+UseSerialGC', '-XX:-UsePerfData', '-Xss256k', '-Xms16m',
                   f'-Xmx{heap}m', '-XX:ReservedCodeCacheSize=16m', '-XX:MaxMetaspaceSize=64m',
                   '-cp', '/work', 'Main']
Path('/tmp/input.txt').write_text(payload['input'], encoding='utf-8')
fd = os.open('/tmp/input.txt', os.O_RDONLY)
os.dup2(fd, 0)
os.close(fd)
# Only the compiler/runtime inside the container receives student source/artifacts.
os.execvpe(command[0], command, env)
