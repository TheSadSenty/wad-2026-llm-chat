"""Database configuration helpers."""

from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import get_settings


def _is_sqlite_url(database_url: str) -> bool:
    """Return whether the URL points to SQLite."""
    return database_url.startswith('sqlite')


def create_db_engine(database_url: str | None = None) -> Engine:
    """Create a SQLAlchemy engine for the configured database."""
    resolved_url = database_url or get_settings().database_url
    connect_args = {'check_same_thread': False} if _is_sqlite_url(resolved_url) else {}
    return create_engine(resolved_url, connect_args=connect_args)


engine = create_db_engine()
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)


def get_db_session() -> Generator[Session]:
    """Yield a request-scoped database session."""
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
