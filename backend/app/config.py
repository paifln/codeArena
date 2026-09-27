"""Validated deployment configuration; signing keys never have a default."""
from functools import lru_cache
from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    secret_key: SecretStr
    cookie_secure: bool = False
    run_cooldown_seconds: float = Field(default=2, ge=0)
    submit_cooldown_seconds: float = Field(default=5, ge=0)
    max_queue_size: int = Field(default=200, ge=1, le=200)
    judge_concurrency: int = Field(default=2, ge=1, le=4)

    @field_validator("secret_key")
    @classmethod
    def strong_key(cls, value):
        raw = value.get_secret_value()
        if len(raw) != 128 or any(c not in "0123456789abcdefABCDEF" for c in raw):
            raise ValueError("SECRET_KEY must be a random 64-byte hexadecimal value")
        return value


@lru_cache
def settings():
    return Settings()
