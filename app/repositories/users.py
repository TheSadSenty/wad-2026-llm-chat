from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.user import User


def get_user_by_login(session: Session, login: str) -> User | None:
    """Fetch a user by login."""
    statement = select(User).where(User.login == login)
    return session.execute(statement).scalar_one_or_none()


def create_user(session: Session, *, login: str, password_hash: str) -> User:
    """Persist a new user."""
    user = User(login=login, password_hash=password_hash)
    session.add(user)
    session.commit()
    session.refresh(user)
    return user
