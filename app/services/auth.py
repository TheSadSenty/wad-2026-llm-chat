from sqlalchemy.orm import Session

from app.models.user import User
from app.repositories.users import create_user, get_user_by_login
from app.services.security import hash_password, verify_password

AUTH_COOKIE_NAME = 'llm_chat_user_id'


class RegistrationConflictError(Exception):
    """Raised when the registration email is already in use."""


class InvalidCredentialsError(Exception):
    """Raised when a login attempt uses invalid credentials."""


def register_user(*, session: Session, login: str, password: str) -> User:
    """Register a new user if the login is still available."""
    if get_user_by_login(session, login) is not None:
        raise RegistrationConflictError

    return create_user(
        session,
        login=login,
        password_hash=hash_password(password),
    )


def authenticate_user(*, session: Session, login: str, password: str) -> User:
    """Validate login credentials and return the matching user."""
    user = get_user_by_login(session, login)
    if user is None or not verify_password(password, user.password_hash):
        raise InvalidCredentialsError

    return user
