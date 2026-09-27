import time
from dataclasses import dataclass, field
from .comparators import equivalent
from .languages import PythonRunner, CompiledRunner
from .limits import Limits, MAX_TESTS, SUBMISSION_BUDGET_SECONDS
from .sandbox import DockerSandbox
from .verdicts import Verdict


@dataclass
class Judgement:
    verdict: str
    tests: list[dict] = field(default_factory=list)
    time_ms: int = 0
    memory_kb: int = 0
    error: str = ''
    score: float = 0


def judge(source, language, snapshot, kind='SUBMIT', custom_input=None, sandbox=None):
    sandbox = sandbox or DockerSandbox()
    if language not in ('python3', 'cpp20', 'java17'):
        return Judgement(Verdict.SYSTEM_ERROR, error='Unsupported language')
    ready, detail = sandbox.available()
    if not ready:
        return Judgement(Verdict.SYSTEM_ERROR, error=detail)
    try:
        limits = Limits(float(snapshot.get('time_limit', 2)), int(snapshot.get('mem_limit', 256)))
        tests = snapshot.get('tests', [])
        if kind == 'RUN':
            tests = ([{'input_data': custom_input, 'is_sample': True}]
                     if custom_input is not None else [test for test in tests if test.get('is_sample')])
        if not tests or len(tests) > MAX_TESTS:
            return Judgement(Verdict.SYSTEM_ERROR, error='No eligible tests or too many tests')
        partial = kind == 'SUBMIT' and snapshot.get('scoring') == 'PARTIAL'
        total_weight = sum(t.get('weight', 1) for t in tests)
        earned = 0
        runner = PythonRunner(sandbox) if language == 'python3' else CompiledRunner(sandbox, language)
        runner.prepare(source)
        started = time.monotonic()
        result = Judgement(Verdict.ACCEPTED)
        try:
            compilation = runner.compile()
            if compilation.verdict != Verdict.ACCEPTED:
                return Judgement(Verdict.SYSTEM_ERROR if compilation.verdict == Verdict.SYSTEM_ERROR else Verdict.COMPILATION_ERROR, error=compilation.stderr[:4096])
            for ordinal, test in enumerate(tests, 1):
                if time.monotonic() - started + limits.time_seconds + 15 > SUBMISSION_BUDGET_SECONDS:
                    result.verdict = Verdict.SYSTEM_ERROR
                    result.error = 'Submission execution budget exhausted; reduce the test suite'
                    break
                execution = runner.execute(test.get('input_data', ''), limits)
                verdict = execution.verdict
                if verdict == Verdict.ACCEPTED and 'expected' in test and not equivalent(execution.stdout, test['expected']):
                    verdict = Verdict.WRONG_ANSWER
                result.tests.append({'ordinal': ordinal, 'verdict': str(verdict),
                                     'stdout': execution.stdout, 'stderr': execution.stderr,
                                     'time_ms': execution.time_ms, 'memory_kb': execution.memory_kb,
                                     'is_sample': bool(test.get('is_sample'))})
                result.time_ms = max(result.time_ms, execution.time_ms)
                result.memory_kb = max(result.memory_kb, execution.memory_kb)
                if verdict == Verdict.ACCEPTED:
                    earned += test.get('weight', 1)
                if verdict != Verdict.ACCEPTED:
                    result.verdict = verdict
                    if not partial or verdict == Verdict.SYSTEM_ERROR:
                        break
            if result.verdict != Verdict.SYSTEM_ERROR:
                result.score = (round(100 * earned / total_weight, 2) if partial and total_weight
                                else 100 if result.verdict == Verdict.ACCEPTED else 0)
                if partial and 0 < result.score < 100:
                    result.verdict = Verdict.PARTIAL
                elif partial and result.score == 100:
                    result.verdict = Verdict.ACCEPTED
            return result
        finally:
            runner.cleanup()
    except (TypeError, ValueError, KeyError):
        return Judgement(Verdict.SYSTEM_ERROR, error='Invalid judging snapshot')
