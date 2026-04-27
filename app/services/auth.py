from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.repositories.users import create_user, get_user_by_id as get_user_by_id_query, get_user_by_login
from app.services.security import hash_password, verify_password

AUTH_COOKIE_NAME = 'llm_chat_user_id'


class RegistrationConflictError(Exception):
    """Raised when the registration email is already in use."""


class InvalidCredentialsError(Exception):
    """Raised when a login attempt uses invalid credentials."""


async def get_user_by_id(session: AsyncSession, user_id: int) -> User | None:
    """Fetch a user by primary key."""
    return await get_user_by_id_query(session, user_id)


async def register_user_async(*, session: AsyncSession, login: str, password: str) -> User:
    """Register a new user account."""
    if await get_user_by_login(session, login) is not None:
        raise RegistrationConflictError

    return await create_user(
        session,
        login=login,
        password_hash=hash_password(password),
    )


async def authenticate_user_async(*, session: AsyncSession, login: str, password: str) -> User:
    """Authenticate a user."""
    user = await get_user_by_login(session, login)
    if user is None or not verify_password(password, user.password_hash):
        raise InvalidCredentialsError

    return user
