from datetime import datetime
from uuid import UUID
from typing import Literal
from pydantic import BaseModel, Field, model_validator, ConfigDict


class Input(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Login(Input):
    username: str = Field(min_length=3, max_length=50, pattern=r"^[a-zA-Z0-9_.-]+$")
    password: str = Field(min_length=1, max_length=256)


class Setup(Login):
    organization: str = Field(min_length=2, max_length=120)
    name: str = Field(min_length=2, max_length=100)
    password: str = Field(min_length=10, max_length=256)
    language: Literal["ru", "kk", "en"] = "ru"


class UserCreate(Login):
    name: str = Field(min_length=2, max_length=100)
    role: Literal["TEACHER", "STUDENT"] = "STUDENT"
    password: str = Field(min_length=10, max_length=256)


class GroupCreate(Input):
    name: str = Field(min_length=1, max_length=100)


class PasswordChange(Input):
    old_password: str = Field(min_length=1, max_length=256)
    new_password: str = Field(min_length=10, max_length=256)


class Members(Input):
    user_ids: list[int] = Field(min_length=1, max_length=200)


class BulkStudents(Input):
    prefix: str = Field(min_length=2, max_length=30, pattern=r"^[a-zA-Z0-9_.-]+$")
    count: int = Field(ge=1, le=100)


class TestIn(Input):
    input_data: str = Field(default="", max_length=64000)
    expected: str = Field(default="", max_length=64000)
    is_sample: bool = False


class ProblemIn(Input):
    title: str = Field(min_length=2, max_length=200)
    description: str = Field(min_length=10, max_length=30000)
    input_fmt: str = Field(default="", max_length=5000)
    output_fmt: str = Field(default="", max_length=5000)
    constraints: str = Field(default="", max_length=5000)
    difficulty: Literal["EASY", "MEDIUM", "HARD"] = "EASY"
    time_limit: float = Field(default=2, ge=0.1, le=10)
    mem_limit: int = Field(default=128, ge=32, le=512)
    tags: list[str] = Field(default_factory=list, max_length=12)
    translations: dict = Field(default_factory=dict)
    tests: list[TestIn] = Field(min_length=1, max_length=50)

    @model_validator(mode="after")
    def sample_required(self):
        if not any(t.is_sample for t in self.tests):
            raise ValueError("At least one sample test is required")
        if (
            sum(
                len(t.input_data.encode()) + len(t.expected.encode())
                for t in self.tests
            )
            > 512000
        ):
            raise ValueError("Tests exceed 512 KB")
        if any(len(t) > 40 for t in self.tags):
            raise ValueError("Tag exceeds 40 characters")
        return self


class ContestIn(Input):
    title: str = Field(min_length=2, max_length=200)
    description: str = Field(default="", max_length=10000)
    rules: str = Field(default="", max_length=10000)
    start_time: datetime
    end_time: datetime
    problem_ids: list[int] = Field(min_length=1, max_length=26)
    group_ids: list[int] = Field(default_factory=list, max_length=50)
    participant_ids: list[int] = Field(default_factory=list, max_length=500)
    scoreboard_enabled: bool = True
    show_problem_difficulty: bool = True

    @model_validator(mode="after")
    def dates(self):
        if not self.start_time.tzinfo or not self.end_time.tzinfo:
            raise ValueError("Dates require a timezone")
        if self.end_time <= self.start_time:
            raise ValueError("End must be after start")
        if (self.end_time - self.start_time).total_seconds() > 604800:
            raise ValueError("Maximum duration is 7 days")
        if not self.group_ids and not self.participant_ids:
            raise ValueError("Assign a group or student")
        if len(set(self.problem_ids)) != len(self.problem_ids):
            raise ValueError("Duplicate problems")
        return self


class Extend(Input):
    minutes: int = Field(ge=1, le=1440)


class SubmitIn(Input):
    request_id: UUID | None = None
    contest_id: int
    problem_id: int
    source: str = Field(min_length=1, max_length=50000)
    language: Literal["python3"] = "python3"
    kind: Literal["RUN", "SUBMIT"] = "SUBMIT"
    custom_input: str | None = Field(default=None, max_length=64000)

    @model_validator(mode="after")
    def source_bytes(self):
        if len(self.source.encode("utf-8")) > 128 * 1024:
            raise ValueError("Source exceeds 128 KB")
        return self


class Question(Input):
    question: str = Field(min_length=3, max_length=3000)
    problem_id: int | None = None


class Answer(Input):
    answer: str = Field(min_length=1, max_length=5000)
    is_public: bool = False


class AnnouncementIn(Input):
    message: str = Field(min_length=1, max_length=5000)
    level: Literal["INFO", "WARNING", "IMPORTANT"] = "INFO"
