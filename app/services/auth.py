from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.repositories.users import create_user, get_user_by_login
from app.repositories.users import get_user_by_id as get_user_by_id_query
from app.services.security import (
    JwtDecodeError,
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)

AUTH_COOKIE_NAME = 'llm_chat_access_token'


class RegistrationConflictError(Exception):
    """Raised when the registration email is already in use."""


class InvalidCredentialsError(Exception):
    """Raised when a login attempt uses invalid credentials."""


def get_current_user_from_request(request: Request) -> User | None:
    """Return the authenticated user attached by auth middleware."""
    current_user = getattr(request.state, 'current_user', None)
    if current_user is None or not isinstance(current_user, User):
        return None

    return current_user


def get_access_token_from_request(request: Request) -> str | None:
    """Read the access token from the Authorization header or auth cookie."""
    authorization = request.headers.get('Authorization')
    if authorization is not None:
        scheme, _, token = authorization.partition(' ')
        if scheme.lower() == 'bearer' and token:
            return token

    return request.cookies.get(AUTH_COOKIE_NAME)


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


def create_user_access_token(user: User) -> str:
    """Create a JWT access token for a user."""
    return create_access_token(user_id=user.id)


async def get_user_from_access_token(session: AsyncSession, token: str) -> User | None:
    """Resolve a JWT access token to a user."""
    try:
        user_id = decode_access_token(token)
    except JwtDecodeError:
        return None

    return await get_user_by_id(session, user_id)
