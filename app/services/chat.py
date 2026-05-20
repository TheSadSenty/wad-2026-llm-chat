import json
from collections.abc import AsyncIterator
from dataclasses import dataclass
from http import HTTPStatus

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.csat import Chat
from app.repositories.chats import add_chat, add_message, get_chat_for_user, list_chats_for_user
from app.services.llm import get_llm_service


@dataclass(frozen=True, slots=True)
class ChatPageServiceResult:
    """Data required to render the chat page."""

    chats: list[Chat]
    selected_chat: Chat | None
    error_message: str | None = None
    prompt: str = ''
    status_code: int = HTTPStatus.OK


@dataclass(frozen=True, slots=True)
class ChatRedirectServiceResult:
    """Redirect target returned by a chat service action."""

    location: str
    status_code: int = HTTPStatus.SEE_OTHER


@dataclass(frozen=True, slots=True)
class ChatTextServiceResult:
    """Plain-text error payload for streaming endpoints."""

    message: str
    status_code: int


@dataclass(frozen=True, slots=True)
class ChatStreamServiceResult:
    """SSE stream returned by a chat service action."""

    event_stream: AsyncIterator[str]


class ChatNotFoundError(Exception):
    """Raised when a chat does not belong to the current user."""


def _build_chat_title(prompt: str) -> str:
    shortened_prompt = ' '.join(prompt.split())
    if len(shortened_prompt) <= 48:
        return shortened_prompt

    return f'{shortened_prompt[:45].rstrip()}...'


async def list_user_chats(*, session: AsyncSession, user_id: int) -> list[Chat]:
    """Return persisted chats for a user."""
    return await list_chats_for_user(session, user_id=user_id)


async def get_user_chat(*, session: AsyncSession, user_id: int, chat_id: int) -> Chat | None:
    """Return a single chat for a user."""
    return await get_chat_for_user(session, chat_id=chat_id, user_id=user_id)


async def create_chat_with_user_message(*, session: AsyncSession, user_id: int, prompt: str) -> Chat:
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


async def append_user_message(
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


async def persist_assistant_reply(
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


async def create_chat_with_llm_reply(*, session: AsyncSession, user_id: int, prompt: str) -> Chat:
    """Create a new chat and persist an LLM-generated assistant reply."""
    chat = await create_chat_with_user_message(session=session, user_id=user_id, prompt=prompt)
    assistant_reply = await get_llm_service().generate_reply(messages=chat.messages)
    persisted_chat = await persist_assistant_reply(
        session=session,
        user_id=user_id,
        chat_id=chat.id,
        content=assistant_reply,
    )
    if persisted_chat is None:
        msg = 'Chat not found.'
        raise RuntimeError(msg)

    return persisted_chat


async def append_llm_reply(*, session: AsyncSession, user_id: int, chat_id: int, prompt: str) -> Chat:
    """Append a user message and an LLM-generated assistant reply."""
    updated_chat = await append_user_message(session=session, user_id=user_id, chat_id=chat_id, prompt=prompt)
    if updated_chat is None:
        msg = 'Chat not found.'
        raise RuntimeError(msg)

    assistant_reply = await get_llm_service().generate_reply(messages=updated_chat.messages)
    persisted_chat = await persist_assistant_reply(
        session=session,
        user_id=user_id,
        chat_id=updated_chat.id,
        content=assistant_reply,
    )
    if persisted_chat is None:
        msg = 'Chat not found.'
        raise RuntimeError(msg)

    return persisted_chat


async def build_chat_page(
    *,
    session: AsyncSession,
    user_id: int | None,
    chat_id: int | None,
) -> ChatPageServiceResult:
    """Collect the data needed to render the chat page."""
    if user_id is None:
        return ChatPageServiceResult(chats=[], selected_chat=None)

    chats = await list_user_chats(session=session, user_id=user_id)
    selected_chat = chats[0] if chats else None
    if chat_id is not None:
        selected_chat = await get_user_chat(session=session, user_id=user_id, chat_id=chat_id)
        if selected_chat is None:
            raise ChatNotFoundError

    return ChatPageServiceResult(chats=chats, selected_chat=selected_chat)


async def handle_chat_creation(
    *,
    session: AsyncSession,
    user_id: int,
    prompt: str,
) -> ChatPageServiceResult | ChatRedirectServiceResult:
    """Create a new chat or return a page state describing the error."""
    normalized_prompt = prompt.strip()
    if not normalized_prompt:
        chats = await list_user_chats(session=session, user_id=user_id)
        return ChatPageServiceResult(
            chats=chats,
            selected_chat=chats[0] if chats else None,
            error_message='Message cannot be empty.',
            status_code=HTTPStatus.UNPROCESSABLE_ENTITY,
        )

    try:
        chat = await create_chat_with_llm_reply(session=session, user_id=user_id, prompt=normalized_prompt)
    except RuntimeError as error:
        chats = await list_user_chats(session=session, user_id=user_id)
        return ChatPageServiceResult(
            chats=chats,
            selected_chat=chats[0] if chats else None,
            error_message=str(error),
            prompt=normalized_prompt,
            status_code=HTTPStatus.SERVICE_UNAVAILABLE,
        )

    return ChatRedirectServiceResult(location=f'/chats?chat_id={chat.id}')


async def handle_message_submission(
    *,
    session: AsyncSession,
    user_id: int,
    chat_id: int,
    prompt: str,
) -> ChatPageServiceResult | ChatRedirectServiceResult:
    """Append a message to an existing chat or return a page state describing the error."""
    chat = await get_user_chat(session=session, user_id=user_id, chat_id=chat_id)
    if chat is None:
        raise ChatNotFoundError

    normalized_prompt = prompt.strip()
    if not normalized_prompt:
        chats = await list_user_chats(session=session, user_id=user_id)
        return ChatPageServiceResult(
            chats=chats,
            selected_chat=chat,
            error_message='Message cannot be empty.',
            status_code=HTTPStatus.UNPROCESSABLE_ENTITY,
        )

    try:
        await append_llm_reply(session=session, user_id=user_id, chat_id=chat.id, prompt=normalized_prompt)
    except RuntimeError as error:
        chats = await list_user_chats(session=session, user_id=user_id)
        selected_chat = await get_user_chat(session=session, user_id=user_id, chat_id=chat_id)
        return ChatPageServiceResult(
            chats=chats,
            selected_chat=selected_chat,
            error_message=str(error),
            prompt=normalized_prompt,
            status_code=HTTPStatus.SERVICE_UNAVAILABLE,
        )

    return ChatRedirectServiceResult(location=f'/chats?chat_id={chat_id}')


async def start_chat_creation_stream(
    *,
    session: AsyncSession,
    user_id: int,
    prompt: str,
) -> ChatTextServiceResult | ChatStreamServiceResult:
    """Create a chat and return an SSE stream for the assistant reply."""
    normalized_prompt = prompt.strip()
    if not normalized_prompt:
        return ChatTextServiceResult(
            message='Message cannot be empty.',
            status_code=HTTPStatus.UNPROCESSABLE_ENTITY,
        )

    try:
        chat = await create_chat_with_user_message(session=session, user_id=user_id, prompt=normalized_prompt)
    except RuntimeError as error:
        return ChatTextServiceResult(
            message=str(error),
            status_code=HTTPStatus.SERVICE_UNAVAILABLE,
        )

    return ChatStreamServiceResult(
        event_stream=_stream_assistant_reply(
            session=session,
            user_id=user_id,
            chat=chat,
        ),
    )


async def start_message_stream(
    *,
    session: AsyncSession,
    user_id: int,
    chat_id: int,
    prompt: str,
) -> ChatTextServiceResult | ChatStreamServiceResult:
    """Append a user message and return an SSE stream for the assistant reply."""
    chat = await get_user_chat(session=session, user_id=user_id, chat_id=chat_id)
    if chat is None:
        return ChatTextServiceResult(
            message='Chat not found.',
            status_code=HTTPStatus.NOT_FOUND,
        )

    normalized_prompt = prompt.strip()
    if not normalized_prompt:
        return ChatTextServiceResult(
            message='Message cannot be empty.',
            status_code=HTTPStatus.UNPROCESSABLE_ENTITY,
        )

    updated_chat = await append_user_message(
        session=session,
        user_id=user_id,
        chat_id=chat.id,
        prompt=normalized_prompt,
    )
    if updated_chat is None:
        return ChatTextServiceResult(
            message='Chat not found.',
            status_code=HTTPStatus.NOT_FOUND,
        )

    return ChatStreamServiceResult(
        event_stream=_stream_assistant_reply(
            session=session,
            user_id=user_id,
            chat=updated_chat,
        ),
    )


def _sse_event(event: str, data: dict[str, object]) -> str:
    payload = json.dumps(data)
    return f'event: {event}\ndata: {payload}\n\n'


async def _stream_assistant_reply(
    *,
    session: AsyncSession,
    user_id: int,
    chat: Chat,
) -> AsyncIterator[str]:
    """Generate and persist an assistant reply while streaming SSE events."""
    assistant_parts: list[str] = []
    try:
        yield _sse_event(
            'meta',
            {
                'chat_id': chat.id,
                'chat_title': chat.title,
                'chat_url': f'/chats?chat_id={chat.id}',
                'message_count': len(chat.messages),
            },
        )
        async for token in get_llm_service().stream_reply(messages=chat.messages):
            assistant_parts.append(token)
            yield _sse_event('token', {'text': token})

        final_reply = ''.join(assistant_parts).strip()
        if not final_reply:
            msg = 'The local model returned an empty response.'
            raise RuntimeError(msg)

        updated_chat = await persist_assistant_reply(
            session=session,
            user_id=user_id,
            chat_id=chat.id,
            content=final_reply,
        )
        if updated_chat is None:
            msg = 'Chat not found.'
            raise RuntimeError(msg)

        yield _sse_event(
            'done',
            {
                'chat_id': updated_chat.id,
                'chat_url': f'/chats?chat_id={updated_chat.id}',
                'message_count': len(updated_chat.messages),
            },
        )
    except Exception as error:
        yield _sse_event('error', {'message': str(error)})
