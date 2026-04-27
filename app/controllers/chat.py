from typing import Annotated

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db import get_db_session
from app.models.csat import Chat
from app.models.user import User
from app.repositories.users import get_user_by_id
from app.services.auth import AUTH_COOKIE_NAME
from app.services.chat import append_llm_reply, create_chat_with_llm_reply, get_user_chat, list_user_chats

chat_router = APIRouter(tags=['chat'])
templates = Jinja2Templates(directory='app/templates')


class ChatPromptForm(BaseModel):
    """User prompt submitted from the chat form."""

    prompt: str


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
