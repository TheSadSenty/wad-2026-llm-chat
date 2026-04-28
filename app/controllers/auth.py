from http import HTTPStatus
from typing import Annotated

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db import get_db_session
from app.forms import LoginForm, RegistrationForm
from app.services.auth import (
    AUTH_COOKIE_NAME,
    GithubEmailNotAvailableError,
    GithubOAuthConfigurationError,
    GithubOAuthError,
    GithubOAuthStateError,
    InvalidCredentialsError,
    RegistrationConflictError,
    authenticate_user_async,
    authenticate_with_github_async,
    create_user_access_token,
    get_github_authorization_url,
    register_user_async,
    validate_github_oauth_state,
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
            'github_oauth_enabled': get_settings().auth.github.oauth_enabled,
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
            'github_oauth_enabled': get_settings().auth.github.oauth_enabled,
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
            'github_oauth_enabled': get_settings().auth.github.oauth_enabled,
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
    """Authenticate a user and issue a JWT-backed auth cookie."""
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
    max_age = get_settings().auth.access_token_ttl_minutes * 60
    response.set_cookie(
        key=AUTH_COOKIE_NAME,
        value=create_user_access_token(user),
        httponly=True,
        samesite='lax',
        max_age=max_age,
    )
    return response


@auth_router.get('/auth/github', response_model=None)
async def github_login(request: Request) -> RedirectResponse | HTMLResponse:
    """Redirect the browser to GitHub's OAuth authorization screen."""
    redirect_uri = str(request.url_for('github_callback'))
    try:
        authorization_url = get_github_authorization_url(redirect_uri=redirect_uri)
    except GithubOAuthConfigurationError:
        return _render_login_page(
            request,
            error_message='GitHub OAuth is not configured on this server.',
            status_code=HTTPStatus.SERVICE_UNAVAILABLE,
        )

    return RedirectResponse(url=authorization_url, status_code=HTTPStatus.SEE_OTHER)


@auth_router.get('/auth/github/callback', response_model=None)
async def github_callback(
    request: Request,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
) -> RedirectResponse | HTMLResponse:
    """Handle the GitHub OAuth callback and sign the user into the app."""
    if error is not None:
        return _render_login_page(
            request,
            error_message='GitHub authorization was denied or failed.',
            status_code=HTTPStatus.UNAUTHORIZED,
        )

    if code is None or state is None:
        return _render_login_page(
            request,
            error_message='GitHub did not return a valid authorization response.',
            status_code=HTTPStatus.BAD_REQUEST,
        )

    redirect_uri = str(request.url_for('github_callback'))
    try:
        validate_github_oauth_state(state=state, redirect_uri=redirect_uri)
        user = await authenticate_with_github_async(session=session, code=code, redirect_uri=redirect_uri)
    except GithubOAuthConfigurationError:
        return _render_login_page(
            request,
            error_message='GitHub OAuth is not configured on this server.',
            status_code=HTTPStatus.SERVICE_UNAVAILABLE,
        )
    except GithubOAuthStateError:
        return _render_login_page(
            request,
            error_message='The GitHub login state is invalid or expired. Please try again.',
            status_code=HTTPStatus.BAD_REQUEST,
        )
    except GithubEmailNotAvailableError:
        return _render_login_page(
            request,
            error_message='Your GitHub account does not expose a verified email address for sign-in.',
            status_code=HTTPStatus.UNPROCESSABLE_ENTITY,
        )
    except GithubOAuthError as error:
        return _render_login_page(
            request,
            error_message=str(error),
            status_code=HTTPStatus.BAD_GATEWAY,
        )

    response = RedirectResponse(url='/chats', status_code=HTTPStatus.SEE_OTHER)
    max_age = get_settings().auth.access_token_ttl_minutes * 60
    response.set_cookie(
        key=AUTH_COOKIE_NAME,
        value=create_user_access_token(user),
        httponly=True,
        samesite='lax',
        max_age=max_age,
    )
    return response


@auth_router.post('/logout', response_model=None)
async def logout() -> RedirectResponse:
    """Clear the JWT auth cookie."""
    response = RedirectResponse(url='/login', status_code=HTTPStatus.SEE_OTHER)
    response.delete_cookie(AUTH_COOKIE_NAME)
    return response
