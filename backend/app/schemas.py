from datetime import datetime
from uuid import UUID
from typing import Literal, Annotated
from pydantic import BaseModel, Field, model_validator, ConfigDict, field_validator


class Input(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


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


class PasswordReset(Input):
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
    weight: int = Field(default=1, ge=0, le=100)


class ProblemIn(Input):
    title: str = Field(min_length=2, max_length=200)
    description: str = Field(min_length=10, max_length=30000)
    input_fmt: str = Field(default="", max_length=5000)
    output_fmt: str = Field(default="", max_length=5000)
    constraints: str = Field(default="", max_length=5000)
    difficulty: Literal["EASY", "MEDIUM", "HARD"] = "EASY"
    time_limit: float = Field(default=2, ge=0.1, le=10)
    mem_limit: int = Field(default=128, ge=32, le=512)
    tags: list[Annotated[str, Field(min_length=1, max_length=40)]] = Field(
        default_factory=list, max_length=12
    )
    translations: dict[
        Literal["ru", "kk", "en"],
        dict[
            Literal["title", "description", "input_fmt", "output_fmt", "constraints"],
            Annotated[str, Field(max_length=30000)],
        ],
    ] = Field(default_factory=dict, max_length=3)
    tests: list[TestIn] = Field(min_length=1, max_length=50)
    editorial: str = Field(default="", max_length=30000)

    @model_validator(mode="after")
    def sample_required(self):
        if not any(t.weight > 0 for t in self.tests):
            raise ValueError("At least one test must have a positive weight")
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


class TeamIn(Input):
    name: str = Field(min_length=1, max_length=100)
    organization: str = Field(default="", max_length=120)
    user_ids: list[int] = Field(min_length=1, max_length=6)


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
    mode: Literal["INDIVIDUAL", "TEAM"] = "INDIVIDUAL"
    scoring: Literal["ICPC", "EDUCATIONAL", "PARTIAL"] = "ICPC"
    practice_enabled: bool = False
    teams: list[TeamIn] = Field(default_factory=list, max_length=200)
    penalty_minutes: int = Field(default=20, ge=0, le=120)
    freeze_minutes: int = Field(default=0, ge=0, le=1440)
    languages: list[
        Literal["python3", "cpp20", "java17", "javascript", "go", "csharp"]
    ] = Field(
        default_factory=lambda: ["python3", "cpp20", "java17"],
        min_length=1,
        max_length=6,
    )
    public_scoreboard: bool = False

    @field_validator("start_time", "end_time", mode="before")
    @classmethod
    def wire_datetime(cls, value):
        # JSON has no native datetime; explicitly accept ISO strings only.
        return (
            datetime.fromisoformat(value.replace("Z", "+00:00"))
            if isinstance(value, str)
            else value
        )

    @model_validator(mode="after")
    def dates(self):
        if not self.start_time.tzinfo or not self.end_time.tzinfo:
            raise ValueError("Dates require a timezone")
        if self.end_time <= self.start_time:
            raise ValueError("End must be after start")
        if (
            self.freeze_minutes * 60
            >= (self.end_time - self.start_time).total_seconds()
        ):
            raise ValueError("Freeze must be shorter than the contest")
        if (self.end_time - self.start_time).total_seconds() > 604800:
            raise ValueError("Maximum duration is 7 days")
        if self.mode == "TEAM":
            ids = [uid for team in self.teams for uid in team.user_ids]
            if (
                not ids
                or len(ids) != len(set(ids))
                or self.group_ids
                or self.participant_ids
            ):
                raise ValueError(
                    "Team contests require unique team members and no individual/group assignments"
                )
            if len({t.name.casefold() for t in self.teams}) != len(self.teams):
                raise ValueError("Team names must be unique")
        elif self.teams:
            raise ValueError("Teams require TEAM mode")
        if not self.group_ids and not self.participant_ids and not self.teams:
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
    source: str = Field(min_length=1, max_length=65536)
    language: Literal["python3", "cpp20", "java17", "javascript", "go", "csharp"] = (
        "python3"
    )
    practice: bool = False
    kind: Literal["RUN", "SUBMIT"] = "SUBMIT"
    custom_input: str | None = Field(default=None, max_length=64000)

    @field_validator("request_id", mode="before")
    @classmethod
    def wire_uuid(cls, value):
        return UUID(value) if isinstance(value, str) else value

    @model_validator(mode="after")
    def source_bytes(self):
        if len(self.source.encode("utf-8")) > 64 * 1024:
            raise ValueError("Source exceeds 64 KB")
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


class FeedbackIn(Input):
    feedback: str = Field(max_length=5000)


class PracticeSettings(Input):
    practice_enabled: bool


class DisplaySettings(Input):
    public_scoreboard: bool


class RejudgeIn(Input):
    problem_id: int | None = None
    affected_only: bool = False


class TeamsCSV(Input):
    csv: str = Field(min_length=1, max_length=100000)


class LogoIn(Input):
    data: str = Field(max_length=700000)


class ExternalProblemIn(Input):
    url: str = Field(max_length=500)
    html: str | None = Field(default=None, max_length=2_000_000)


class ContestLanguages(Input):
    languages: list[
        Literal["python3", "cpp20", "java17", "javascript", "go", "csharp"]
    ] = Field(min_length=1, max_length=6)
