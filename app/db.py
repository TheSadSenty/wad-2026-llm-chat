"""Database configuration helpers."""

from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

from app.config import get_settings


def create_db_engine(database_url: str | None = None) -> AsyncEngine:
    """Create an async SQLAlchemy engine for the configured database."""
    resolved_url = database_url or get_settings().database_url
    return create_async_engine(resolved_url)


engine = create_db_engine()
SessionLocal = async_sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


async def get_db_session() -> AsyncIterator[AsyncSession]:
    """Yield a request-scoped async database session."""
    async with SessionLocal() as session:
        yield session
