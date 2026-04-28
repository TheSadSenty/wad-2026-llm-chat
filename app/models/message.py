from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.csat import Chat


MAX_ROLE_NAME_LENGTH = 32


class Message(Base):
    """Single message in a chat thread."""

    __tablename__ = 'messages'

    id: Mapped[int] = mapped_column(primary_key=True)
    chat_id: Mapped[int] = mapped_column(ForeignKey('chats.id', ondelete='CASCADE'), index=True)
    role: Mapped[str] = mapped_column(String(MAX_ROLE_NAME_LENGTH))
    content: Mapped[str] = mapped_column(Text())  # noqa:WPS110
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    chat: Mapped[Chat] = relationship(back_populates='messages')
