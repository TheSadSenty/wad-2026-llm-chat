from functools import lru_cache
from pathlib import Path
from typing import Any, Self, override
from urllib.parse import quote_plus

from pydantic import BaseModel
from pydantic_settings import (
    BaseSettings,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
    TomlConfigSettingsSource,
)

CONFIG_FILE_NAME = 'config.toml'


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
    allow_signup: bool


class AuthConfig(BaseModel):
    """Authentication configuration."""

    jwt_secret: str
    access_token_ttl_minutes: int
    github: GithubAuthConfig | None = None


class Config(BaseSettings):
    """Runtime configuration."""

    app: AppConfig
    auth: AuthConfig
    database: DatabaseConfig
    llm: LlmConfig

    model_config = SettingsConfigDict(
        env_prefix='LLM_CHAT_',
        env_nested_delimiter='__',
        env_ignore_empty=True,
        case_sensitive=False,
        validate_default=True,
        extra='ignore',
        toml_file=CONFIG_FILE_NAME,
        frozen=True,
    )

    @classmethod
    def load_config(cls, **kwargs: Any) -> Self:
        """Load config."""
        return cls(**kwargs)

    @override
    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        """Load defaults from TOML and allow environment variables to override them."""
        return (env_settings, TomlConfigSettingsSource(settings_cls))

    @property
    def database_url(self) -> str:
        """Return the SQLAlchemy connection URL."""
        return self.database.postgres.database_url


@lru_cache(maxsize=1)
def get_settings() -> Config:
    """Return cached application settings."""
    return Config.load_config()
