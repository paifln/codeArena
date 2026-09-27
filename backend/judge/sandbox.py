"""Docker is the only execution backend. No host-code fallback exists."""

import json
import math
import os
import subprocess
import threading
import time
import uuid
from dataclasses import dataclass
from typing import Protocol

from .limits import Limits, MAX_INPUT_BYTES, MAX_OUTPUT_BYTES, MAX_SOURCE_BYTES
from .verdicts import Verdict


@dataclass
class Execution:
    verdict: str = Verdict.ACCEPTED
    stdout: str = ""
    stderr: str = ""
    time_ms: int = 0
    memory_kb: int = (
        0  # Docker CLI cannot reliably measure peak RSS; never fabricate it.
    )
    artifact: str = ""


class Sandbox(Protocol):
    def available(self) -> tuple[bool, str]: ...
    def run(
        self,
        source: str,
        stdin: str,
        limits: Limits,
        *,
        compile_only: bool = False,
        language: str = "python3",
        artifact: str = "",
    ) -> Execution: ...


class DockerSandbox:
    def __init__(self, image: str | None = None):
        self.image = image or os.environ.get("SANDBOX_IMAGE", "codearena-sandbox:local")

    def _command(self, *args, timeout=10):
        return subprocess.run(
            ["docker", *args], capture_output=True, timeout=timeout, check=False
        )

    def available(self):
        try:
            info = self._command("info", "--format", "{{json .}}")
            if info.returncode:
                return False, "Docker Linux engine is unavailable"
            capabilities = json.loads(info.stdout)
            if capabilities.get("OSType") != "linux":
                return False, "Docker Linux engine is unavailable"
            if not any(
                str(option).startswith("name=seccomp")
                for option in capabilities.get("SecurityOptions", [])
            ):
                return False, "Docker seccomp isolation is required"
            # Docker can accept resource flags but merely warn when the host's
            # cgroups cannot enforce them. Such runtimes must never become ready.
            required = (
                "MemoryLimit",
                "SwapLimit",
                "PidsLimit",
                "CpuCfsQuota",
                "CpuCfsPeriod",
            )
            if not all(capabilities.get(capability) is True for capability in required):
                return (
                    False,
                    "Docker requires working memory, swap, PID and CPU cgroup limits",
                )
            inspected = self._command("image", "inspect", self.image)
            if inspected.returncode:
                return False, "Build the sandbox image with Docker Compose"
            return True, "Docker sandbox ready"
        except (
            OSError,
            ValueError,
            TypeError,
            AttributeError,
            subprocess.TimeoutExpired,
        ):
            return False, "Docker runtime is unavailable"

    def create_args(self, name: str, limits: Limits, language="python3"):
        return [
            "create",
            "--name",
            name,
            "--label",
            "codearena.sandbox=true",
            "--label",
            f"codearena.expires={int(time.time()) + 60}",
            "-i",
            "--network",
            "none",
            "--read-only",
            "--user",
            "10001:10001",
            "--cap-drop",
            "ALL",
            "--security-opt",
            "no-new-privileges:true",
            "--memory",
            f"{limits.memory_mb}m",
            "--memory-swap",
            f"{limits.memory_mb}m",
            "--cpus",
            "1",
            "--pids-limit",
            "32" if language in ("java17", "javascript", "go", "csharp") else "16",
            "--log-driver",
            "none",
            "--ulimit",
            "nofile=64:64",
            "--ulimit",
            "core=0:0",
            "--ulimit",
            f"cpu={math.ceil(limits.time_seconds) + 1}:{math.ceil(limits.time_seconds) + 1}",
            "--tmpfs",
            "/tmp:rw,noexec,nosuid,nodev,size=16m,mode=1777",
            "--tmpfs",
            "/work:rw,exec,nosuid,nodev,size=96m,mode=1777",
            "--entrypoint",
            "python",
            self.image,
            "-I",
            "-B",
            "/opt/codearena/bootstrap.py",
        ]

    def cleanup_expired(self):
        """Collect containers orphaned by a worker crash, never touch other workloads."""
        result = self._command(
            "ps",
            "-a",
            "--filter",
            "label=codearena.sandbox=true",
            "--format",
            '{{.ID}} {{.Label "codearena.expires"}}',
        )
        if result.returncode:
            return
        for line in result.stdout.decode().splitlines():
            parts = line.split()
            if len(parts) == 2 and parts[1].isdigit() and int(parts[1]) < time.time():
                self._command("rm", "-f", parts[0])

    def run(
        self,
        source,
        stdin,
        limits,
        *,
        compile_only=False,
        language="python3",
        artifact="",
    ):
        if (
            len(source.encode()) > MAX_SOURCE_BYTES
            or len(stdin.encode()) > MAX_INPUT_BYTES
        ):
            return Execution(
                Verdict.SYSTEM_ERROR, stderr="Execution input exceeds configured limits"
            )
        name = f"codearena-{uuid.uuid4().hex}"
        process = None
        buffers = [bytearray(), bytearray()]
        overflow = threading.Event()
        threads = []
        started = time.monotonic()
        try:
            created = self._command(*self.create_args(name, limits, language))
            if created.returncode:
                return Execution(
                    Verdict.SYSTEM_ERROR, stderr="Could not create isolated container"
                )
            process = subprocess.Popen(
                ["docker", "start", "-a", "-i", name],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )

            def drain(stream, target):
                while True:
                    block = stream.read(4096)
                    if not block:
                        break
                    ceiling = (
                        6 * 1024 * 1024
                        if compile_only and target is buffers[0]
                        else MAX_OUTPUT_BYTES
                    )
                    room = ceiling - len(target)
                    target.extend(block[: max(0, room)])
                    if len(block) > room:
                        overflow.set()

            for stream, target in zip((process.stdout, process.stderr), buffers):
                thread = threading.Thread(
                    target=drain, args=(stream, target), daemon=True
                )
                thread.start()
                threads.append(thread)
            payload = json.dumps(
                {
                    "source": source,
                    "input": stdin,
                    "language": language,
                    "artifact": artifact,
                    "memory_mb": limits.memory_mb,
                    "mode": "compile" if compile_only else "execute",
                }
            ).encode()

            # Feed on a separate thread: a broken runtime must not block the lease forever.
            def feed():
                try:
                    process.stdin.write(payload)
                    process.stdin.close()
                except (OSError, ValueError):
                    pass

            feeder = threading.Thread(target=feed, daemon=True)
            feeder.start()
            started = time.monotonic()
            verdict = Verdict.ACCEPTED
            # A fixed 1 s allowance covers Docker attach/bootstrap overhead. CPU is independently bounded.
            while process.poll() is None:
                if overflow.is_set():
                    verdict = Verdict.OUTPUT_LIMIT_EXCEEDED
                    break
                if time.monotonic() - started > limits.time_seconds + 1:
                    verdict = Verdict.TIME_LIMIT_EXCEEDED
                    break
                time.sleep(0.02)
            if process.poll() is None:
                self._command("kill", name)
                process.kill()
            process.wait(timeout=5)
            for thread in threads:
                thread.join(timeout=2)
            if overflow.is_set():
                verdict = Verdict.OUTPUT_LIMIT_EXCEEDED
            inspected = self._command("inspect", "--format", "{{json .State}}", name)
            if inspected.returncode:
                verdict = Verdict.SYSTEM_ERROR
            else:
                state = json.loads(inspected.stdout)
                if state.get("OOMKilled"):
                    verdict = Verdict.MEMORY_LIMIT_EXCEEDED
                elif verdict == Verdict.ACCEPTED and state.get("ExitCode", 1) != 0:
                    if state.get("ExitCode") in (137, 152):
                        verdict = Verdict.TIME_LIMIT_EXCEEDED
                    else:
                        verdict = (
                            Verdict.COMPILATION_ERROR
                            if compile_only
                            else Verdict.RUNTIME_ERROR
                        )
            output = buffers[0].decode("utf-8", "replace")
            compiled = (
                output
                if compile_only
                and language != "python3"
                and verdict == Verdict.ACCEPTED
                else ""
            )
            return Execution(
                verdict,
                "" if compiled else output,
                buffers[1].decode("utf-8", "replace"),
                int((time.monotonic() - started) * 1000),
                artifact=compiled,
            )
        except (OSError, ValueError, subprocess.TimeoutExpired):
            return Execution(
                Verdict.SYSTEM_ERROR,
                stderr="Isolated runtime failed; retry when judge is healthy",
            )
        finally:
            if process is not None and process.poll() is None:
                process.kill()
            try:
                self._command("rm", "-f", name)
            except (OSError, subprocess.TimeoutExpired):
                pass
