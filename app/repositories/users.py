from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User


async def get_user_by_login(session: AsyncSession, login: str) -> User | None:
    """Fetch a user by login."""
    statement = select(User).where(User.login == login)
    return (await session.execute(statement)).scalar_one_or_none()


async def get_user_by_id(session: AsyncSession, user_id: int) -> User | None:
    """Fetch a user by primary key."""
    return await session.get(User, user_id)


async def create_user(session: AsyncSession, *, login: str, password_hash: str) -> User:
    """Persist a new user."""
    user = User(login=login, password_hash=password_hash)
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user
