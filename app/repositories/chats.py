from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.csat import Chat
from app.models.message import Message


async def list_chats_for_user(session: AsyncSession, *, user_id: int) -> list[Chat]:
    """Return all chats owned by a user, newest first."""
    statement = (
        select(Chat).options(selectinload(Chat.messages)).where(Chat.user_id == user_id).order_by(Chat.id.desc())
    )
    return list((await session.scalars(statement)).all())


async def get_chat_for_user(session: AsyncSession, *, chat_id: int, user_id: int) -> Chat | None:
    """Return a chat only if it belongs to the given user."""
    statement = select(Chat).options(selectinload(Chat.messages)).where(Chat.id == chat_id, Chat.user_id == user_id)
    return (await session.execute(statement)).scalar_one_or_none()


async def add_chat(session: AsyncSession, *, user_id: int, title: str) -> Chat:
    """Create a chat in the current transaction."""
    chat = Chat(user_id=user_id, title=title)
    session.add(chat)
    await session.flush()
    return chat


async def add_message(session: AsyncSession, *, chat_id: int, role: str, content: str) -> Message:
    """Create a chat message in the current transaction."""
    message = Message(chat_id=chat_id, role=role, content=content)
    session.add(message)
    await session.flush()
    return message
