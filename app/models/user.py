from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.csat import Chat


class User(Base):
    """Registered user."""

    __tablename__ = 'users'

    id: Mapped[int] = mapped_column(primary_key=True)
    login: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(512))
    github_user_id: Mapped[int | None] = mapped_column(unique=True, index=True)
    github_username: Mapped[str | None] = mapped_column(String(255))
    chats: Mapped[list[Chat]] = relationship(back_populates='user', cascade='all, delete-orphan')
