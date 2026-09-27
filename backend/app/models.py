import time
from sqlalchemy import (
    Column,
    Integer,
    String,
    Text,
    Float,
    Boolean,
    JSON,
    ForeignKey,
    UniqueConstraint,
    CheckConstraint,
    Index,
    LargeBinary,
)
from .db import Base


class Timestamps:
    created_at = Column(Float, default=time.time, nullable=False)
    updated_at = Column(Float, default=time.time, onupdate=time.time, nullable=False)


class User(Timestamps, Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    username = Column(String(50), unique=True, nullable=False)
    name = Column(String(100), nullable=False)
    password_hash = Column(Text, nullable=False)
    role = Column(String(16), nullable=False)
    creator_id = Column(Integer, ForeignKey("users.id"))
    active = Column(Boolean, default=True, nullable=False)
    last_seen = Column(Float, default=0)
    __table_args__ = (CheckConstraint("role IN ('ADMIN','TEACHER','STUDENT')"),)


class Session(Base):
    __tablename__ = "sessions"
    id = Column(String(64), primary_key=True)
    user_id = Column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    csrf = Column(String(64), nullable=False)
    expires_at = Column(Float, nullable=False)


class RefreshToken(Base):
    __tablename__ = "refresh_tokens"
    id = Column(String(64), primary_key=True)
    session_id = Column(String(64), nullable=False, index=True)
    user_id = Column(Integer, nullable=False, index=True)
    expires_at = Column(Float, nullable=False)
    revoked = Column(Boolean, default=False, nullable=False)


class Group(Timestamps, Base):
    __tablename__ = "groups"
    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False)
    author_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    __table_args__ = (UniqueConstraint("author_id", "name"),)


class GroupMember(Base):
    __tablename__ = "group_members"
    group_id = Column(
        Integer, ForeignKey("groups.id", ondelete="CASCADE"), primary_key=True
    )
    user_id = Column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )


class Problem(Timestamps, Base):
    __tablename__ = "problems"
    id = Column(Integer, primary_key=True)
    title = Column(String(200), nullable=False)
    slug = Column(String(240), unique=True, nullable=False)
    description = Column(Text, nullable=False)
    input_fmt = Column(Text, default="")
    output_fmt = Column(Text, default="")
    constraints = Column(Text, default="")
    difficulty = Column(String(10), nullable=False)
    time_limit = Column(Float, default=2, nullable=False)
    mem_limit = Column(Integer, default=128, nullable=False)
    author_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    tags = Column(JSON, default=list, nullable=False)
    translations = Column(JSON, default=dict, nullable=False)
    version = Column(Integer, default=1, nullable=False)
    editorial = Column(Text, default="", nullable=False)
    __table_args__ = (
        CheckConstraint("difficulty IN ('EASY','MEDIUM','HARD')"),
        CheckConstraint("time_limit > 0 AND time_limit <= 10"),
        CheckConstraint("mem_limit >= 32 AND mem_limit <= 512"),
    )


class ProblemDocument(Base):
    __tablename__ = "problem_documents"
    id = Column(Integer, primary_key=True)
    problem_id = Column(
        Integer,
        ForeignKey("problems.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name = Column(String(180), nullable=False)
    media_type = Column(String(100), nullable=False)
    size = Column(Integer, nullable=False)
    data = Column(LargeBinary, nullable=False)
    created_at = Column(Float, default=time.time, nullable=False)


class TestCase(Base):
    __tablename__ = "test_cases"
    id = Column(Integer, primary_key=True)
    problem_id = Column(
        Integer,
        ForeignKey("problems.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    ordinal = Column(Integer, nullable=False)
    input_data = Column(Text, nullable=False)
    expected = Column(Text, nullable=False)
    is_sample = Column(Boolean, default=False, nullable=False)
    weight = Column(Integer, default=1, nullable=False)
    __table_args__ = (UniqueConstraint("problem_id", "ordinal"),)


class Contest(Timestamps, Base):
    __tablename__ = "contests"
    id = Column(Integer, primary_key=True)
    title = Column(String(200), nullable=False)
    description = Column(Text, default="")
    rules = Column(Text, default="")
    author_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    start_time = Column(Float, nullable=False, index=True)
    end_time = Column(Float, nullable=False, index=True)
    status = Column(String(16), default="SCHEDULED", nullable=False)
    paused_at = Column(Float)
    paused_seconds = Column(Float, default=0, nullable=False)
    freeze_at = Column(Float)
    scoreboard_enabled = Column(Boolean, default=True, nullable=False)
    show_problem_difficulty = Column(Boolean, default=True, nullable=False)
    mode = Column(String(16), default="INDIVIDUAL", nullable=False)
    scoring = Column(String(16), default="ICPC", nullable=False)
    practice_enabled = Column(Boolean, default=False, nullable=False)
    penalty_minutes = Column(Integer, default=20, nullable=False)
    languages = Column(
        JSON, default=lambda: ["python3", "cpp20", "java17"], nullable=False
    )
    public_scoreboard = Column(Boolean, default=False, nullable=False)
    logo_data = Column(Text, default="", nullable=False)
    revealed_ids = Column(JSON, default=list, nullable=False)
    __table_args__ = (
        CheckConstraint("end_time > start_time"),
        CheckConstraint(
            "status IN ('DRAFT','SCHEDULED','RUNNING','PAUSED','FINISHED','ARCHIVED')"
        ),
    )


class ContestProblem(Base):
    __tablename__ = "contest_problems"
    contest_id = Column(
        Integer, ForeignKey("contests.id", ondelete="CASCADE"), primary_key=True
    )
    problem_id = Column(Integer, ForeignKey("problems.id"), primary_key=True)
    ordinal = Column(Integer, nullable=False)


class ContestGroup(Base):
    __tablename__ = "contest_groups"
    contest_id = Column(
        Integer, ForeignKey("contests.id", ondelete="CASCADE"), primary_key=True
    )
    group_id = Column(Integer, ForeignKey("groups.id"), primary_key=True)


class ContestParticipant(Base):
    __tablename__ = "contest_participants"
    contest_id = Column(
        Integer, ForeignKey("contests.id", ondelete="CASCADE"), primary_key=True
    )
    user_id = Column(Integer, ForeignKey("users.id"), primary_key=True)


class Submission(Timestamps, Base):
    __tablename__ = "submissions"
    id = Column(Integer, primary_key=True)
    request_id = Column(String(36))
    team_id = Column(Integer, ForeignKey("teams.id"))
    is_practice = Column(Boolean, default=False, nullable=False)
    score = Column(Float, default=0, nullable=False)
    feedback = Column(Text, default="", nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    problem_id = Column(Integer, ForeignKey("problems.id"), nullable=False)
    contest_id = Column(Integer, ForeignKey("contests.id"), nullable=False)
    source = Column(Text, nullable=False)
    language = Column(String(16), default="python3", nullable=False)
    kind = Column(String(8), default="SUBMIT", nullable=False)
    status = Column(String(40), default="QUEUED", nullable=False, index=True)
    custom_input = Column(Text)
    problem_snapshot = Column(JSON, nullable=False)
    contest_elapsed = Column(Float, default=0, nullable=False)
    started_at = Column(Float)
    finished_at = Column(Float)
    lease_token = Column(String(64))
    attempt_count = Column(Integer, default=0, nullable=False)
    time_ms = Column(Integer, default=0, nullable=False)
    memory_kb = Column(Integer, default=0, nullable=False)
    error = Column(Text, default="")
    history = Column(JSON, default=list, nullable=False)
    __table_args__ = (
        Index("ix_submission_user_request", "user_id", "request_id", unique=True),
        Index(
            "ix_submission_contest_user_problem_time",
            "contest_id",
            "user_id",
            "problem_id",
            "created_at",
        ),
        CheckConstraint("kind IN ('RUN','SUBMIT')"),
    )


class SubmissionTestResult(Base):
    __tablename__ = "submission_test_results"
    id = Column(Integer, primary_key=True)
    submission_id = Column(
        Integer,
        ForeignKey("submissions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    ordinal = Column(Integer, nullable=False)
    verdict = Column(String(40), nullable=False)
    time_ms = Column(Integer, default=0)
    memory_kb = Column(Integer, default=0)
    stdout = Column(Text, default="")
    stderr = Column(Text, default="")
    is_sample = Column(Boolean, default=False)
    __table_args__ = (UniqueConstraint("submission_id", "ordinal"),)


class Clarification(Timestamps, Base):
    __tablename__ = "clarifications"
    id = Column(Integer, primary_key=True)
    contest_id = Column(Integer, ForeignKey("contests.id"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    problem_id = Column(Integer, ForeignKey("problems.id"))
    question = Column(Text, nullable=False)
    answer = Column(Text, default="")
    is_public = Column(Boolean, default=False, nullable=False)
    status = Column(String(16), default="OPEN", nullable=False)


class Announcement(Timestamps, Base):
    __tablename__ = "announcements"
    id = Column(Integer, primary_key=True)
    contest_id = Column(Integer, ForeignKey("contests.id"), nullable=False, index=True)
    author_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    message = Column(Text, nullable=False)
    level = Column(String(16), default="INFO", nullable=False)


class AuditLog(Base):
    __tablename__ = "audit_logs"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    action = Column(String(80), nullable=False)
    entity_id = Column(Integer)
    contest_id = Column(Integer, ForeignKey("contests.id"), index=True)
    detail = Column(JSON, default=dict)
    created_at = Column(Float, default=time.time, nullable=False)


class SystemSetting(Base):
    __tablename__ = "system_settings"
    key = Column(String(80), primary_key=True)
    value = Column(JSON, nullable=False)


class RateLimit(Base):
    __tablename__ = "rate_limits"
    key = Column(String(200), primary_key=True)
    count = Column(Integer, default=0, nullable=False)
    reset_at = Column(Float, nullable=False)


class Team(Base):
    __tablename__ = "teams"
    id = Column(Integer, primary_key=True)
    contest_id = Column(
        Integer, ForeignKey("contests.id", ondelete="CASCADE"), nullable=False
    )
    name = Column(String(100), nullable=False)
    organization = Column(String(120), default="", nullable=False)
    created_at = Column(Float, default=time.time, nullable=False)
    __table_args__ = (UniqueConstraint("contest_id", "name"),)


class TeamMember(Base):
    __tablename__ = "team_members"
    contest_id = Column(
        Integer, ForeignKey("contests.id", ondelete="CASCADE"), primary_key=True
    )
    user_id = Column(Integer, ForeignKey("users.id"), primary_key=True)
    team_id = Column(
        Integer, ForeignKey("teams.id", ondelete="CASCADE"), nullable=False
    )


class ContestPresence(Base):
    __tablename__ = "contest_presence"
    contest_id = Column(
        Integer, ForeignKey("contests.id", ondelete="CASCADE"), primary_key=True
    )
    user_id = Column(Integer, ForeignKey("users.id"), primary_key=True)
    last_seen = Column(Float, nullable=False)
    connected = Column(Boolean, default=True, nullable=False)


class PuzzleReward(Base):
    __tablename__ = "puzzle_rewards"
    id = Column(Integer, primary_key=True)
    contest_id = Column(Integer, ForeignKey("contests.id"), nullable=False, index=True)
    identity = Column(String(40), nullable=False)
    problem_id = Column(Integer, ForeignKey("problems.id"), nullable=False)
    submission_id = Column(Integer, ForeignKey("submissions.id"), nullable=False)
    solved_at = Column(Float, nullable=False)
    delivered_at = Column(Float)
    delivered_by = Column(Integer, ForeignKey("users.id"))
    revoked = Column(Boolean, default=False, nullable=False)
    __table_args__ = (UniqueConstraint("contest_id", "identity", "problem_id"),)


class RejudgeBatch(Base):
    __tablename__ = "rejudge_batches"
    id = Column(Integer, primary_key=True)
    contest_id = Column(Integer, ForeignKey("contests.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    remaining_ids = Column(JSON, default=list, nullable=False)
    total = Column(Integer, nullable=False)
    created_at = Column(Float, default=time.time, nullable=False)
    finished_at = Column(Float)
