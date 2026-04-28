from http import HTTPStatus
from typing import Annotated
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db import get_db_session
from app.models.user import User
from app.schemas import LoginRequest, RegisterRequest, TokenPair
from app.services.auth import (
    GithubEmailNotAvailableError,
    GithubOAuthConfigurationError,
    GithubOAuthError,
    GithubOAuthStateError,
    InvalidCredentialsError,
    RegistrationConflictError,
    authenticate_user,
    authenticate_with_github,
    get_github_authorization_url,
    issue_tokens,
    logout,
    refresh_tokens,
    register_user,
    validate_github_oauth_state,
)

auth_router = APIRouter(prefix='/api/auth', tags=['auth'])
auth_pages_router = APIRouter(tags=['auth-pages'])
templates = Jinja2Templates(directory='app/templates')


@auth_pages_router.get('/login', response_class=HTMLResponse, response_model=None)
async def login_page(request: Request) -> HTMLResponse:
    """Render the login page used by the browser frontend."""
    return templates.TemplateResponse(
        request=request,
        name='auth/login.html',
        context={
            'error_message': None,
            'login': '',
            'github_oauth_enabled': bool(get_settings().auth.github),
        },
    )


@auth_pages_router.get('/register', response_class=HTMLResponse, response_model=None)
async def register_page(request: Request) -> HTMLResponse:
    """Render the registration page used by the browser frontend."""
    return templates.TemplateResponse(
        request=request,
        name='auth/register.html',
        context={
            'error_message': None,
            'success_message': None,
            'login': '',
            'github_oauth_enabled': bool(get_settings().auth.github),
        },
    )


@auth_router.post('/register', response_model=TokenPair, status_code=HTTPStatus.CREATED)
async def register(
    payload: RegisterRequest,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> TokenPair:
    """Register a new user account and issue a token pair."""
    try:
        created_user = await register_user(
            session=session,
            login=str(payload.login),
            password=payload.password,
        )
    except RegistrationConflictError:
        raise HTTPException(
            status_code=HTTPStatus.CONFLICT,
            detail='A user with this email already exists.',
        )

    return TokenPair.model_validate(await issue_tokens(created_user))


@auth_router.post('/login', response_model=TokenPair)
async def login(
    payload: LoginRequest,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> TokenPair:
    """Authenticate a user and issue a token pair."""
    try:
        user = await authenticate_user(
            session=session,
            login=str(payload.login),
            password=payload.password,
        )
    except InvalidCredentialsError:
        raise HTTPException(
            status_code=HTTPStatus.UNAUTHORIZED,
            detail='Invalid email or password.',
        )

    return TokenPair.model_validate(await issue_tokens(user))


@auth_router.post('/refresh', response_model=TokenPair)
async def refresh(
    session: Annotated[AsyncSession, Depends(get_db_session)],
    refresh_token: str = Query(...),
) -> TokenPair:
    """Rotate a refresh token and issue a fresh token pair."""
    try:
        tokens = await refresh_tokens(session=session, refresh_token=refresh_token)
    except InvalidCredentialsError:
        raise HTTPException(
            status_code=HTTPStatus.UNAUTHORIZED,
            detail='Invalid refresh token.',
        )

    return TokenPair.model_validate(tokens)


@auth_router.get('/github/login', response_model=None)
async def github_login(request: Request) -> RedirectResponse | HTMLResponse:
    """Redirect the browser to GitHub's OAuth authorization screen."""
    redirect_uri = str(request.url_for('github_callback'))
    try:
        authorization_url = get_github_authorization_url(redirect_uri=redirect_uri)
    except GithubOAuthConfigurationError:
        return _github_error_page(
            request=request,
            error_message='GitHub OAuth is not configured on this server.',
            status_code=HTTPStatus.SERVICE_UNAVAILABLE,
        )

    return RedirectResponse(url=authorization_url, status_code=HTTPStatus.SEE_OTHER)


@auth_router.get('/github/callback', response_model=None)
async def github_callback(
    request: Request,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    code: str,
    state: str,
    error: str | None = None,
) -> RedirectResponse | HTMLResponse:
    """Handle the GitHub OAuth callback and sign the user into the app."""
    invalid_response = _validate_github_callback_request(
        request=request,
        code=code,
        state=state,
        error=error,
    )
    if invalid_response is not None:
        return invalid_response

    redirect_uri = str(request.url_for('github_callback'))
    try:
        user = await _authenticate_github_callback(
            session=session,
            state=state,
            code=code,
            redirect_uri=redirect_uri,
        )
    except GithubOAuthConfigurationError:
        return _github_error_page(
            request=request,
            error_message='GitHub OAuth is not configured on this server.',
            status_code=HTTPStatus.SERVICE_UNAVAILABLE,
        )
    except GithubOAuthStateError:
        return _github_error_page(
            request=request,
            error_message='The GitHub login state is invalid or expired. Please try again.',
            status_code=HTTPStatus.BAD_REQUEST,
        )
    except GithubEmailNotAvailableError:
        return _github_error_page(
            request=request,
            error_message='Your GitHub account does not expose a verified email address for sign-in.',
            status_code=HTTPStatus.UNPROCESSABLE_ENTITY,
        )
    except GithubOAuthError as github_oauth_error:
        return _github_error_page(
            request=request,
            error_message=str(github_oauth_error),
            status_code=HTTPStatus.BAD_GATEWAY,
        )

    tokens = await issue_tokens(user)
    redirect_url = '/login?' + urlencode(tokens)
    return RedirectResponse(url=redirect_url, status_code=HTTPStatus.SEE_OTHER)


@auth_router.post('/logout', response_model=None)
async def logout_route(refresh_token: str = Query(...)) -> dict[str, str]:
    """Delete a refresh session."""
    await logout(refresh_token)
    return {'status': 'ok'}


def _validate_github_callback_request(
    *,
    request: Request,
    code: str | None,
    state: str | None,
    error: str | None,
) -> HTMLResponse | None:
    if error is not None:
        return _github_error_page(
            request=request,
            error_message='GitHub authorization was denied or failed.',
            status_code=HTTPStatus.UNAUTHORIZED,
        )

    if code is None or state is None:
        return _github_error_page(
            request=request,
            error_message='GitHub did not return a valid authorization response.',
            status_code=HTTPStatus.BAD_REQUEST,
        )

    return None


async def _authenticate_github_callback(
    *,
    session: AsyncSession,
    state: str,
    code: str,
    redirect_uri: str,
) -> User:
    validate_github_oauth_state(state=state, redirect_uri=redirect_uri)
    return await authenticate_with_github(
        session=session,
        code=code,
        redirect_uri=redirect_uri,
    )


def _github_error_page(
    *,
    request: Request,
    error_message: str,
    status_code: HTTPStatus,
) -> HTMLResponse:
    return templates.TemplateResponse(
        request=request,
        name='auth/login.html',
        context={
            'error_message': error_message,
            'login': '',
            'github_oauth_enabled': bool(get_settings().auth.github),
        },
        status_code=status_code,
    )
