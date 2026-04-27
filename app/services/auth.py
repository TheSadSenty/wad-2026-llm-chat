from sqlalchemy.orm import Session

from app.models.user import User
from app.repositories.users import create_user, get_user_by_login
from app.services.security import hash_password


class RegistrationConflictError(Exception):
    """Raised when the registration email is already in use."""


def register_user(*, session: Session, login: str, password: str) -> User:
    """Register a new user if the login is still available."""
    if get_user_by_login(session, login) is not None:
        raise RegistrationConflictError

    return create_user(
        session,
        login=login,
        password_hash=hash_password(password),
    )
