"""Redis client for refresh-session storage."""

from functools import lru_cache

from redis.asyncio import Redis

from app.config import get_settings


@lru_cache(maxsize=1)
def get_redis_client() -> Redis:
    """Create and cache the async Redis client."""
    settings = get_settings()
    return Redis(
        host=settings.redis.host,
        port=settings.redis.port,
        db=settings.redis.db,
        password=settings.redis.password,
        decode_responses=True,
    )


redis_client = get_redis_client()
