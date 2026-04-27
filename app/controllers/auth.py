from http import HTTPStatus
from typing import Annotated

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db_session
from app.forms import LoginForm, RegistrationForm
from app.services.auth import (
    AUTH_COOKIE_NAME,
    InvalidCredentialsError,
    RegistrationConflictError,
    authenticate_user_async,
    register_user_async,
)

auth_router = APIRouter(tags=['auth'])
templates = Jinja2Templates(directory='app/templates')


def _render_registration_page(
    request: Request,
    *,
    error_message: str | None = None,
    login: str = '',
    status_code: int = HTTPStatus.OK,
) -> HTMLResponse:
    return templates.TemplateResponse(
        request=request,
        name='auth/register.html',
        context={
            'error_message': error_message,
            'login': login,
        },
        status_code=status_code,
    )


def _render_login_page(
    request: Request,
    *,
    error_message: str | None = None,
    login: str = '',
    status_code: int = HTTPStatus.OK,
) -> HTMLResponse:
    return templates.TemplateResponse(
        request=request,
        name='auth/login.html',
        context={
            'error_message': error_message,
            'login': login,
        },
        status_code=status_code,
    )


@auth_router.get('/register', response_class=HTMLResponse)
async def registration_form(request: Request) -> HTMLResponse:
    """Render the user registration form."""
    return _render_registration_page(request)


@auth_router.post('/register', response_class=HTMLResponse, status_code=HTTPStatus.CREATED)
async def register(
    request: Request,
    registration_form_data: Annotated[RegistrationForm, Form()],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> HTMLResponse:
    """Register a new user account."""
    try:
        created_user = await register_user_async(
            session=session,
            login=str(registration_form_data.login),
            password=registration_form_data.password,
        )
    except RegistrationConflictError:
        return _render_registration_page(
            request,
            error_message='A user with this email already exists.',
            login=str(registration_form_data.login),
            status_code=HTTPStatus.CONFLICT,
        )

    return templates.TemplateResponse(
        request=request,
        name='auth/register.html',
        context={
            'error_message': None,
            'login': '',
            'success_message': f'User {created_user.login} registered successfully.',
        },
        status_code=HTTPStatus.CREATED,
    )


@auth_router.get('/login', response_class=HTMLResponse)
async def login_form(request: Request) -> HTMLResponse:
    """Render the login form."""
    return _render_login_page(request)


@auth_router.post('/login', response_model=None)
async def login(
    request: Request,
    login_form_data: Annotated[LoginForm, Form()],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> HTMLResponse | RedirectResponse:
    """Authenticate a user and start a browser session."""
    try:
        user = await authenticate_user_async(
            session=session,
            login=str(login_form_data.login),
            password=login_form_data.password,
        )
    except InvalidCredentialsError:
        return _render_login_page(
            request,
            error_message='Invalid email or password.',
            login=str(login_form_data.login),
            status_code=HTTPStatus.UNAUTHORIZED,
        )

    response = RedirectResponse(url='/chats', status_code=HTTPStatus.SEE_OTHER)
    response.set_cookie(
        key=AUTH_COOKIE_NAME,
        value=str(user.id),
        httponly=True,
        samesite='lax',
    )
    return response


@auth_router.post('/logout', response_model=None)
async def logout() -> RedirectResponse:
    """Clear the browser session."""
    response = RedirectResponse(url='/login', status_code=HTTPStatus.SEE_OTHER)
    response.delete_cookie(AUTH_COOKIE_NAME)
    return response
