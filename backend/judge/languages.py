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


class CompiledRunner(PythonRunner):
    def __init__(self, sandbox, language):
        super().__init__(sandbox)
        self.language = language
        self.artifact = ""

    def compile(self):
        result = self.sandbox.run(self.source, "", Limits(10, 512), compile_only=True, language=self.language)
        self.artifact = result.artifact
        return result

    def execute(self, stdin, limits):
        return self.sandbox.run("", stdin, limits, language=self.language, artifact=self.artifact)

    def cleanup(self):
        super().cleanup()
        self.artifact = ""
