import json
from collections.abc import Iterator
from typing import Annotated

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, PlainTextResponse, RedirectResponse, StreamingResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db import get_db_session
from app.models.csat import Chat
from app.models.user import User
from app.repositories.users import get_user_by_id
from app.services.auth import AUTH_COOKIE_NAME
from app.services.chat import (
    append_llm_reply,
    append_user_message,
    create_chat_with_llm_reply,
    create_chat_with_user_message,
    get_user_chat,
    list_user_chats,
    persist_assistant_reply,
)
from app.services.llm import get_llm_service

chat_router = APIRouter(tags=['chat'])
templates = Jinja2Templates(directory='app/templates')


class ChatPromptForm(BaseModel):
    """User prompt submitted from the chat form."""

    prompt: str


def _sse_event(event: str, data: dict[str, object]) -> str:
    payload = json.dumps(data)
    return f'event: {event}\ndata: {payload}\n\n'


def _streaming_response(event_stream: Iterator[str]) -> StreamingResponse:
    return StreamingResponse(
        event_stream,
        media_type='text/event-stream',
        headers={
            'Cache-Control': 'no-cache',
            'Connection': 'keep-alive',
            'X-Accel-Buffering': 'no',
        },
    )


def _redirect_to_login() -> RedirectResponse:
    return RedirectResponse(url='/login', status_code=303)


def _get_current_user(request: Request, session: Session) -> User | None:
    raw_user_id = request.cookies.get(AUTH_COOKIE_NAME)
    if raw_user_id is None or not raw_user_id.isdigit():
        return None

    return get_user_by_id(session, int(raw_user_id))


def _render_chat_page(
    request: Request,
    *,
    user: User,
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
async def index(
    request: Request,
    session: Annotated[Session, Depends(get_db_session)],
) -> RedirectResponse:
    """Redirect the visitor to the correct entry page."""
    current_user = _get_current_user(request, session)
    if current_user is None:
        return RedirectResponse(url='/register', status_code=303)

    return RedirectResponse(url='/chats', status_code=303)


@chat_router.get('/chats', response_class=HTMLResponse, response_model=None)
async def chat_index(
    request: Request,
    session: Annotated[Session, Depends(get_db_session)],
    chat_id: int | None = None,
) -> HTMLResponse | RedirectResponse:
    """Render the chat workspace for the current user."""
    current_user = _get_current_user(request, session)
    if current_user is None:
        return _redirect_to_login()

    chats = list_user_chats(session=session, user=current_user)
    selected_chat = chats[0] if chats else None
    if chat_id is not None:
        selected_chat = get_user_chat(session=session, user=current_user, chat_id=chat_id)
        if selected_chat is None:
            raise HTTPException(status_code=404, detail='Chat not found.')

    return _render_chat_page(
        request,
        user=current_user,
        chats=chats,
        selected_chat=selected_chat,
    )


@chat_router.post('/chats', response_model=None)
async def create_chat(
    request: Request,
    data: Annotated[ChatPromptForm, Form()],
    session: Annotated[Session, Depends(get_db_session)],
) -> RedirectResponse | HTMLResponse:
    """Create a new chat from the first user prompt."""
    current_user = _get_current_user(request, session)
    if current_user is None:
        return _redirect_to_login()

    prompt = data.prompt.strip()
    if not prompt:
        chats = list_user_chats(session=session, user=current_user)
        return _render_chat_page(
            request,
            user=current_user,
            chats=chats,
            selected_chat=chats[0] if chats else None,
            error_message='Message cannot be empty.',
            status_code=422,
        )

    try:
        chat = create_chat_with_llm_reply(session=session, user=current_user, prompt=prompt)
    except RuntimeError as error:
        chats = list_user_chats(session=session, user=current_user)
        return _render_chat_page(
            request,
            user=current_user,
            chats=chats,
            selected_chat=chats[0] if chats else None,
            error_message=str(error),
            prompt=prompt,
            status_code=503,
        )

    return RedirectResponse(url=f'/chats?chat_id={chat.id}', status_code=303)


@chat_router.post('/chats/{chat_id}/messages', response_model=None)
async def send_message(
    request: Request,
    chat_id: int,
    data: Annotated[ChatPromptForm, Form()],
    session: Annotated[Session, Depends(get_db_session)],
) -> RedirectResponse | HTMLResponse:
    """Append a new message to an existing chat."""
    current_user = _get_current_user(request, session)
    if current_user is None:
        return _redirect_to_login()

    chat = get_user_chat(session=session, user=current_user, chat_id=chat_id)
    if chat is None:
        raise HTTPException(status_code=404, detail='Chat not found.')

    prompt = data.prompt.strip()
    if not prompt:
        chats = list_user_chats(session=session, user=current_user)
        selected_chat = get_user_chat(session=session, user=current_user, chat_id=chat_id)
        return _render_chat_page(
            request,
            user=current_user,
            chats=chats,
            selected_chat=selected_chat,
            error_message='Message cannot be empty.',
            status_code=422,
        )

    try:
        append_llm_reply(session=session, chat=chat, prompt=prompt)
    except RuntimeError as error:
        chats = list_user_chats(session=session, user=current_user)
        selected_chat = get_user_chat(session=session, user=current_user, chat_id=chat_id)
        return _render_chat_page(
            request,
            user=current_user,
            chats=chats,
            selected_chat=selected_chat,
            error_message=str(error),
            prompt=prompt,
            status_code=503,
        )

    return RedirectResponse(url=f'/chats?chat_id={chat_id}', status_code=303)


@chat_router.post('/chats/stream', response_class=StreamingResponse, response_model=None)
async def create_chat_stream(
    request: Request,
    data: Annotated[ChatPromptForm, Form()],
    session: Annotated[Session, Depends(get_db_session)],
) -> StreamingResponse | PlainTextResponse | RedirectResponse:
    """Create a chat and stream the assistant response incrementally."""
    current_user = _get_current_user(request, session)
    if current_user is None:
        return _redirect_to_login()

    prompt = data.prompt.strip()
    if not prompt:
        return PlainTextResponse('Message cannot be empty.', status_code=422)

    try:
        chat = create_chat_with_user_message(session=session, user=current_user, prompt=prompt)
    except RuntimeError as error:
        return PlainTextResponse(str(error), status_code=503)

    def event_stream() -> Iterator[str]:
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
            for token in get_llm_service().stream_reply(messages=chat.messages):
                assistant_parts.append(token)
                yield _sse_event('token', {'text': token})

            final_reply = ''.join(assistant_parts).strip()
            if not final_reply:
                msg = 'The local model returned an empty response.'
                raise RuntimeError(msg)

            updated_chat = persist_assistant_reply(session=session, chat=chat, content=final_reply)
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

    return _streaming_response(event_stream())


@chat_router.post('/chats/{chat_id}/messages/stream', response_class=StreamingResponse, response_model=None)
async def send_message_stream(
    request: Request,
    chat_id: int,
    data: Annotated[ChatPromptForm, Form()],
    session: Annotated[Session, Depends(get_db_session)],
) -> StreamingResponse | PlainTextResponse | RedirectResponse:
    """Append a user message and stream the assistant response incrementally."""
    current_user = _get_current_user(request, session)
    if current_user is None:
        return _redirect_to_login()

    chat = get_user_chat(session=session, user=current_user, chat_id=chat_id)
    if chat is None:
        return PlainTextResponse('Chat not found.', status_code=404)

    prompt = data.prompt.strip()
    if not prompt:
        return PlainTextResponse('Message cannot be empty.', status_code=422)

    updated_chat = append_user_message(session=session, chat=chat, prompt=prompt)

    def event_stream() -> Iterator[str]:
        assistant_parts: list[str] = []
        try:
            yield _sse_event(
                'meta',
                {
                    'chat_id': updated_chat.id,
                    'chat_title': updated_chat.title,
                    'chat_url': f'/chats?chat_id={updated_chat.id}',
                    'message_count': len(updated_chat.messages),
                },
            )
            for token in get_llm_service().stream_reply(messages=updated_chat.messages):
                assistant_parts.append(token)
                yield _sse_event('token', {'text': token})

            final_reply = ''.join(assistant_parts).strip()
            if not final_reply:
                msg = 'The local model returned an empty response.'
                raise RuntimeError(msg)

            final_chat = persist_assistant_reply(session=session, chat=updated_chat, content=final_reply)
            yield _sse_event(
                'done',
                {
                    'chat_id': final_chat.id,
                    'chat_url': f'/chats?chat_id={final_chat.id}',
                    'message_count': len(final_chat.messages),
                },
            )
        except Exception as error:
            yield _sse_event('error', {'message': str(error)})

    return _streaming_response(event_stream())
