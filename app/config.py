from functools import lru_cache
from pathlib import Path
from typing import Any, Self
from urllib.parse import quote_plus

from pydantic import BaseModel
from pydantic_settings import BaseSettings, SettingsConfigDict

ENV_FILE_NAME = '.env'


class AppConfig(BaseModel):
    """Application runtime configuration."""

    host: str
    port: int


class PostgresConfig(BaseModel):
    """PostgreSQL connection settings."""

    host: str
    port: int
    dbname: str
    user: str
    password: str

    @property
    def database_url(self) -> str:
        """Build the SQLAlchemy connection URL."""
        encoded_user = quote_plus(self.user)
        encoded_password = quote_plus(self.password)
        encoded_dbname = quote_plus(self.dbname)
        return f'postgresql+psycopg://{encoded_user}:{encoded_password}@{self.host}:{self.port}/{encoded_dbname}'


class DatabaseConfig(BaseModel):
    """Database configuration tree."""

    postgres: PostgresConfig


class LlmConfig(BaseModel):
    """Local LLM configuration."""

    gguf_path: Path


class GithubAuthConfig(BaseModel):
    """Authentication configuration."""

    client_id: str
    client_secret: str


class AuthConfig(BaseModel):
    """Authentication configuration."""

    jwt_secret: str
    access_token_ttl_minutes: int
    refresh_token_ttl_days: int
    github: GithubAuthConfig | None = None


class RedisConfig(BaseModel):
    """Redis connection settings."""

    host: str
    port: int
    db: int
    password: str | None = None


class Config(BaseSettings):
    """Runtime configuration."""

    app: AppConfig
    auth: AuthConfig
    database: DatabaseConfig
    llm: LlmConfig
    redis: RedisConfig

    model_config = SettingsConfigDict(
        env_prefix='LLM_CHAT_',
        env_nested_delimiter='__',
        env_ignore_empty=True,
        case_sensitive=False,
        validate_default=True,
        extra='ignore',
        env_file=ENV_FILE_NAME,
        env_file_encoding='utf-8',
        frozen=True,
    )

    @classmethod
    def load_config(cls, **kwargs: Any) -> Self:
        """Load config."""
        return cls(**kwargs)

    @property
    def database_url(self) -> str:
        """Return the SQLAlchemy connection URL."""
        return self.database.postgres.database_url


@lru_cache(maxsize=1)
def get_settings() -> Config:
    """Return cached application settings."""
    return Config.load_config()
