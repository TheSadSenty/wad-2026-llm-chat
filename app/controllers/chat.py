from collections.abc import AsyncIterator, Iterator
from typing import Annotated

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, PlainTextResponse, RedirectResponse, StreamingResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db_session
from app.forms import ChatPromptForm
from app.models.csat import Chat
from app.models.user import User
from app.services.auth import get_current_user, get_optional_current_user
from app.services.chat import (
    ChatNotFoundError,
    ChatRedirectServiceResult,
    ChatTextServiceResult,
    build_chat_page,
    handle_chat_creation,
    handle_message_submission,
    start_chat_creation_stream,
    start_message_stream,
)

chat_router = APIRouter(tags=['chat'])
templates = Jinja2Templates(directory='app/templates')


def _streaming_response(event_stream: AsyncIterator[str] | Iterator[str]) -> StreamingResponse:
    return StreamingResponse(
        event_stream,
        media_type='text/event-stream',
        headers={
            'Cache-Control': 'no-cache',
            'Connection': 'keep-alive',
            'X-Accel-Buffering': 'no',
        },
    )


def _render_chat_page(
    request: Request,
    *,
    user: User | None,
    chats: list[Chat],
    selected_chat: Chat | None,
    error_message: str | None = None,
    prompt: str = '',
    status_code: int = 200,
) -> HTMLResponse:
    return templates.TemplateResponse(
        request=request,
        name='chat/index.html',
        context={
            'user': user,
            'chats': chats,
            'selected_chat': selected_chat,
            'error_message': error_message,
            'prompt': prompt,
        },
        status_code=status_code,
    )


@chat_router.get('/', include_in_schema=False, response_model=None)
async def index() -> RedirectResponse:
    """Redirect the visitor to the correct entry page."""
    return RedirectResponse(url='/chats', status_code=303)


@chat_router.get('/chats', response_class=HTMLResponse, response_model=None)
async def chat_index(
    request: Request,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    current_user: Annotated[User | None, Depends(get_optional_current_user)],
    chat_id: int | None = None,
) -> HTMLResponse:
    """Render the chat workspace for the current user."""
    try:
        result = await build_chat_page(
            session=session,
            user_id=current_user.id if current_user is not None else None,
            chat_id=chat_id,
        )
    except ChatNotFoundError:
        raise HTTPException(status_code=404, detail='Chat not found.') from None

    return _render_chat_page(
        request,
        user=current_user,
        chats=result.chats,
        selected_chat=result.selected_chat,
        error_message=result.error_message,
        prompt=result.prompt,
        status_code=result.status_code,
    )


@chat_router.post('/chats', response_model=None)
async def create_chat(
    request: Request,
    data: Annotated[ChatPromptForm, Form()],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> RedirectResponse | HTMLResponse:
    """Create a new chat from the first user prompt."""
    result = await handle_chat_creation(
        session=session,
        user_id=current_user.id,
        prompt=data.prompt,
    )
    if isinstance(result, ChatRedirectServiceResult):
        return RedirectResponse(url=result.location, status_code=result.status_code)

    return _render_chat_page(
        request,
        user=current_user,
        chats=result.chats,
        selected_chat=result.selected_chat,
        error_message=result.error_message,
        prompt=result.prompt,
        status_code=result.status_code,
    )


@chat_router.post('/chats/{chat_id}/messages', response_model=None)
async def send_message(
    request: Request,
    chat_id: int,
    data: Annotated[ChatPromptForm, Form()],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> RedirectResponse | HTMLResponse:
    """Append a new message to an existing chat."""
    try:
        result = await handle_message_submission(
            session=session,
            user_id=current_user.id,
            chat_id=chat_id,
            prompt=data.prompt,
        )
    except ChatNotFoundError:
        raise HTTPException(status_code=404, detail='Chat not found.') from None

    if isinstance(result, ChatRedirectServiceResult):
        return RedirectResponse(url=result.location, status_code=result.status_code)

    return _render_chat_page(
        request,
        user=current_user,
        chats=result.chats,
        selected_chat=result.selected_chat,
        error_message=result.error_message,
        prompt=result.prompt,
        status_code=result.status_code,
    )


@chat_router.post('/chats/stream', response_class=StreamingResponse, response_model=None)
async def create_chat_stream(
    data: Annotated[ChatPromptForm, Form()],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> StreamingResponse | PlainTextResponse:
    """Create a chat and stream the assistant response incrementally."""
    result = await start_chat_creation_stream(
        session=session,
        user_id=current_user.id,
        prompt=data.prompt,
    )
    if isinstance(result, ChatTextServiceResult):
        return PlainTextResponse(result.message, status_code=result.status_code)

    return _streaming_response(result.event_stream)


@chat_router.post('/chats/{chat_id}/messages/stream', response_class=StreamingResponse, response_model=None)
async def send_message_stream(
    chat_id: int,
    data: Annotated[ChatPromptForm, Form()],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> StreamingResponse | PlainTextResponse:
    """Append a user message and stream the assistant response incrementally."""
    result = await start_message_stream(
        session=session,
        user_id=current_user.id,
        chat_id=chat_id,
        prompt=data.prompt,
    )
    if isinstance(result, ChatTextServiceResult):
        return PlainTextResponse(result.message, status_code=result.status_code)

    return _streaming_response(result.event_stream)
