from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.csat import Chat

MAX_LOGIN_LENGTH = 320
MAX_GITHUB_USERNAME_LENGTH = 255

MAX_PASSWORD_HASH_LENGTH = 512


class User(Base):
    """Registered user."""

    __tablename__ = 'users'

    id: Mapped[int] = mapped_column(primary_key=True)
    login: Mapped[str] = mapped_column(String(MAX_LOGIN_LENGTH), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(MAX_PASSWORD_HASH_LENGTH))
    github_user_id: Mapped[int | None] = mapped_column(unique=True, index=True)
    github_username: Mapped[str | None] = mapped_column(String(MAX_GITHUB_USERNAME_LENGTH))
    chats: Mapped[list[Chat]] = relationship(back_populates='user', cascade='all, delete-orphan')
