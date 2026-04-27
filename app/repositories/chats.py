from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models.chat import Chat
from app.models.message import Message


def list_chats_for_user(session: Session, *, user_id: int) -> list[Chat]:
    """Return all chats owned by a user, newest first."""
    statement = (
        select(Chat).options(selectinload(Chat.messages)).where(Chat.user_id == user_id).order_by(Chat.id.desc())
    )
    return list(session.scalars(statement))


def get_chat_for_user(session: Session, *, chat_id: int, user_id: int) -> Chat | None:
    """Return a chat only if it belongs to the given user."""
    statement = select(Chat).options(selectinload(Chat.messages)).where(Chat.id == chat_id, Chat.user_id == user_id)
    return session.execute(statement).scalar_one_or_none()


def add_chat(session: Session, *, user_id: int, title: str) -> Chat:
    """Create a chat in the current transaction."""
    chat = Chat(user_id=user_id, title=title)
    session.add(chat)
    session.flush()
    return chat


def add_message(session: Session, *, chat_id: int, role: str, content: str) -> Message:
    """Create a chat message in the current transaction."""
    message = Message(chat_id=chat_id, role=role, content=content)
    session.add(message)
    session.flush()
    return message
