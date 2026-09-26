from typing import Protocol
from .limits import Limits
from .sandbox import Sandbox, Execution


class LanguageRunner(Protocol):
    def prepare(self, source: str) -> None: ...
    def compile(self) -> Execution: ...
    def execute(self, stdin: str, limits: Limits) -> Execution: ...
    def cleanup(self) -> None: ...


class PythonRunner:
    def __init__(self, sandbox: Sandbox):
        self.sandbox = sandbox
        self.source = ''

    def prepare(self, source):
        self.source = source

    def compile(self):
        return self.sandbox.run(self.source, '', Limits(3, 256), compile_only=True)

    def execute(self, stdin, limits):
        return self.sandbox.run(self.source, stdin, limits)

    def cleanup(self):
        self.source = ''
