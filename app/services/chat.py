from sqlalchemy.ext.asyncio import AsyncSession

from app.models.csat import Chat
from app.repositories.chats import add_chat, add_message, get_chat_for_user, list_chats_for_user
from app.services.llm import get_llm_service


def _build_chat_title(prompt: str) -> str:
    shortened_prompt = ' '.join(prompt.split())
    if len(shortened_prompt) <= 48:
        return shortened_prompt

    return f'{shortened_prompt[:45].rstrip()}...'


async def list_user_chats_async(*, session: AsyncSession, user_id: int) -> list[Chat]:
    """Return persisted chats for a user."""
    return await list_chats_for_user(session, user_id=user_id)


async def get_user_chat_async(*, session: AsyncSession, user_id: int, chat_id: int) -> Chat | None:
    """Return a single chat for a user."""
    return await get_chat_for_user(session, chat_id=chat_id, user_id=user_id)


async def create_chat_with_user_message_async(*, session: AsyncSession, user_id: int, prompt: str) -> Chat:
    """Create a new chat and persist only the user message."""
    normalized_prompt = prompt.strip()
    chat = await add_chat(
        session,
        user_id=user_id,
        title=_build_chat_title(normalized_prompt),
    )
    await add_message(session, chat_id=chat.id, role='user', content=normalized_prompt)
    await session.commit()
    return await get_chat_for_user(session, chat_id=chat.id, user_id=user_id) or chat


async def append_user_message_async(
    *,
    session: AsyncSession,
    user_id: int,
    chat_id: int,
    prompt: str,
) -> Chat | None:
    """Persist a new user message."""
    chat = await get_chat_for_user(session, chat_id=chat_id, user_id=user_id)
    if chat is None:
        return None

    normalized_prompt = prompt.strip()
    await add_message(session, chat_id=chat.id, role='user', content=normalized_prompt)
    await session.commit()
    return await get_chat_for_user(session, chat_id=chat.id, user_id=chat.user_id) or chat


async def persist_assistant_reply_async(
    *,
    session: AsyncSession,
    user_id: int,
    chat_id: int,
    content: str,
) -> Chat | None:
    """Persist a generated assistant reply."""
    chat = await get_chat_for_user(session, chat_id=chat_id, user_id=user_id)
    if chat is None:
        return None

    await add_message(session, chat_id=chat.id, role='assistant', content=content)
    await session.commit()
    return await get_chat_for_user(session, chat_id=chat.id, user_id=chat.user_id) or chat


async def create_chat_with_llm_reply_async(*, session: AsyncSession, user_id: int, prompt: str) -> Chat:
    """Create a new chat and persist an LLM-generated assistant reply."""
    chat = await create_chat_with_user_message_async(session=session, user_id=user_id, prompt=prompt)
    assistant_reply = await get_llm_service().generate_reply(messages=chat.messages)
    persisted_chat = await persist_assistant_reply_async(
        session=session,
        user_id=user_id,
        chat_id=chat.id,
        content=assistant_reply,
    )
    if persisted_chat is None:
        msg = 'Chat not found.'
        raise RuntimeError(msg)

    return persisted_chat


async def append_llm_reply_async(*, session: AsyncSession, user_id: int, chat_id: int, prompt: str) -> Chat:
    """Append a user message and an LLM-generated assistant reply."""
    updated_chat = await append_user_message_async(session=session, user_id=user_id, chat_id=chat_id, prompt=prompt)
    if updated_chat is None:
        msg = 'Chat not found.'
        raise RuntimeError(msg)

    assistant_reply = await get_llm_service().generate_reply(messages=updated_chat.messages)
    persisted_chat = await persist_assistant_reply_async(
        session=session,
        user_id=user_id,
        chat_id=updated_chat.id,
        content=assistant_reply,
    )
    if persisted_chat is None:
        msg = 'Chat not found.'
        raise RuntimeError(msg)

    return persisted_chat
