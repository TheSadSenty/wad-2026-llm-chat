"""Database configuration helpers."""

from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

from app.config import get_settings


def _is_sqlite_url(database_url: str) -> bool:
    """Return whether the URL points to SQLite."""
    return database_url.startswith('sqlite')


def _build_async_database_url(database_url: str) -> str:
    """Normalize the configured URL for SQLAlchemy's async engine."""
    if _is_sqlite_url(database_url) and not database_url.startswith('sqlite+aiosqlite'):
        return database_url.replace('sqlite', 'sqlite+aiosqlite', 1)

    return database_url


def create_db_engine(database_url: str | None = None) -> AsyncEngine:
    """Create an async SQLAlchemy engine for the configured database."""
    resolved_url = database_url or get_settings().database_url
    async_database_url = _build_async_database_url(resolved_url)
    connect_args = {'check_same_thread': False} if _is_sqlite_url(resolved_url) else {}
    return create_async_engine(async_database_url, connect_args=connect_args)


engine = create_db_engine()
SessionLocal = async_sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


async def get_db_session() -> AsyncIterator[AsyncSession]:
    """Yield a request-scoped async database session."""
    async with SessionLocal() as session:
        yield session
