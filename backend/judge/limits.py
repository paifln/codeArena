from dataclasses import dataclass

MAX_SOURCE_BYTES = 128 * 1024
MAX_INPUT_BYTES = 1024 * 1024
MAX_OUTPUT_BYTES = 256 * 1024
MAX_TESTS = 100
SUBMISSION_BUDGET_SECONDS = 120
LEASE_SECONDS = 300


@dataclass(frozen=True)
class Limits:
    time_seconds: float = 2.0
    memory_mb: int = 256

    def __post_init__(self):
        if not 0.1 <= self.time_seconds <= 10 or not 32 <= self.memory_mb <= 1024:
            raise ValueError('Unsupported execution limits')
