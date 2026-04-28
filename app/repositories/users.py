from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User


async def get_user_by_login(session: AsyncSession, login: str) -> User | None:
    """Fetch a user by login."""
    statement = select(User).where(User.login == login)
    return (await session.execute(statement)).scalar_one_or_none()


async def get_user_by_github_user_id(session: AsyncSession, github_user_id: int) -> User | None:
    """Fetch a user by GitHub user id."""
    statement = select(User).where(User.github_user_id == github_user_id)
    return (await session.execute(statement)).scalar_one_or_none()


async def get_user_by_id(session: AsyncSession, user_id: int) -> User | None:
    """Fetch a user by primary key."""
    return await session.get(User, user_id)


async def create_user(
    session: AsyncSession,
    *,
    login: str,
    password_hash: str,
    github_user_id: int | None = None,
    github_username: str | None = None,
) -> User:
    """Persist a new user."""
    user = User(
        login=login,
        password_hash=password_hash,
        github_user_id=github_user_id,
        github_username=github_username,
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user


async def update_user_github_identity(
    session: AsyncSession,
    *,
    user: User,
    github_user_id: int,
    github_username: str | None,
) -> User:
    """Attach or refresh GitHub identity fields on an existing user."""
    user.github_user_id = github_user_id
    user.github_username = github_username
    await session.commit()
    await session.refresh(user)
    return user
