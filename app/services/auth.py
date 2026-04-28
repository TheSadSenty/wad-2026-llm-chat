import asyncio
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from urllib.parse import urlencode

import aiohttp
import jwt
from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import GithubAuthConfig, get_settings
from app.models.user import User
from app.repositories.users import (
    create_user,
    get_user_by_github_user_id,
    get_user_by_login,
    update_user_github_identity,
)
from app.repositories.users import get_user_by_id as get_user_by_id_query
from app.services.security import (
    JWT_ALGORITHM,
    JwtDecodeError,
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)

AUTH_COOKIE_NAME = 'llm_chat_access_token'
GITHUB_ACCESS_TOKEN_URL = 'https://github.com/login/oauth/access_token'  # noqa: S105
GITHUB_AUTHORIZE_URL = 'https://github.com/login/oauth/authorize'
GITHUB_EMAILS_URL = 'https://api.github.com/user/emails'
GITHUB_USER_URL = 'https://api.github.com/user'
GITHUB_OAUTH_STATE_TOKEN_TYPE = 'github_oauth_state'  # noqa: S105
GITHUB_OAUTH_STATE_TTL_MINUTES = 10
GITHUB_OAUTH_SCOPE = 'user:email'
GITHUB_HTTP_TIMEOUT_SECONDS = 10


class RegistrationConflictError(Exception):
    """Raised when the registration email is already in use."""


class InvalidCredentialsError(Exception):
    """Raised when a login attempt uses invalid credentials."""


class GithubOAuthConfigurationError(Exception):
    """Raised when GitHub OAuth is not configured."""


class GithubOAuthError(Exception):
    """Raised when the GitHub OAuth flow fails."""

    def __init__(self, message: str = 'GitHub sign-in could not be completed.') -> None:
        super().__init__(message)


class GithubOAuthStateError(Exception):
    """Raised when the GitHub OAuth callback state is invalid."""


class GithubEmailNotAvailableError(Exception):
    """Raised when GitHub does not provide a usable email address."""


@dataclass(frozen=True, slots=True)
class GithubIdentity:
    """GitHub account details required to sign in."""

    github_user_id: int
    github_username: str
    email: str


def get_current_user_from_request(request: Request) -> User | None:
    """Return the authenticated user attached by auth middleware."""
    current_user = getattr(request.state, 'current_user', None)
    if current_user is None or not isinstance(current_user, User):
        return None

    return current_user


def get_access_token_from_request(request: Request) -> str | None:
    """Read the access token from the Authorization header or auth cookie."""
    authorization = request.headers.get('Authorization')
    if authorization is not None:
        scheme, _, token = authorization.partition(' ')
        if scheme.lower() == 'bearer' and token:
            return token

    return request.cookies.get(AUTH_COOKIE_NAME)


async def get_user_by_id(session: AsyncSession, user_id: int) -> User | None:
    """Fetch a user by primary key."""
    return await get_user_by_id_query(session, user_id)


async def register_user(*, session: AsyncSession, login: str, password: str) -> User:
    """Register a new user account."""
    if await get_user_by_login(session, login) is not None:
        raise RegistrationConflictError

    return await create_user(
        session,
        login=login,
        password_hash=hash_password(password),
    )


async def authenticate_user(*, session: AsyncSession, login: str, password: str) -> User:
    """Authenticate a user."""
    user = await get_user_by_login(session, login)
    if user is None or not verify_password(password, user.password_hash):
        raise InvalidCredentialsError

    return user


def create_user_access_token(user: User) -> str:
    """Create a JWT access token for a user."""
    return create_access_token(user_id=user.id)


def get_github_authorization_url(*, redirect_uri: str) -> str:
    """Build the GitHub OAuth authorization URL."""
    settings = get_settings()
    if not settings.auth.github:
        raise GithubOAuthConfigurationError

    query = urlencode(
        {
            'client_id': settings.auth.github.client_id,
            'redirect_uri': redirect_uri,
            'scope': GITHUB_OAUTH_SCOPE,
            'state': create_github_oauth_state(redirect_uri=redirect_uri),
            'allow_signup': str(settings.auth.github.allow_signup).lower(),
        },
    )
    return f'{GITHUB_AUTHORIZE_URL}?{query}'


def create_github_oauth_state(*, redirect_uri: str) -> str:
    """Create a signed OAuth state token for the GitHub callback."""
    settings = get_settings()
    now = datetime.now(tz=UTC)
    expires_at = now + timedelta(minutes=GITHUB_OAUTH_STATE_TTL_MINUTES)
    payload = {
        'type': GITHUB_OAUTH_STATE_TOKEN_TYPE,
        'redirect_uri': redirect_uri,
        'nonce': secrets.token_urlsafe(24),
        'iat': now,
        'exp': expires_at,
    }
    return jwt.encode(payload, settings.auth.jwt_secret, algorithm=JWT_ALGORITHM)


def validate_github_oauth_state(*, state: str, redirect_uri: str) -> None:
    """Validate the signed OAuth state token returned by GitHub."""
    settings = get_settings()
    try:
        payload = jwt.decode(state, settings.auth.jwt_secret, algorithms=[JWT_ALGORITHM])
    except (jwt.ExpiredSignatureError, jwt.InvalidTokenError) as error:
        raise GithubOAuthStateError from error

    if payload.get('type') != GITHUB_OAUTH_STATE_TOKEN_TYPE:
        raise GithubOAuthStateError
    if payload.get('redirect_uri') != redirect_uri:
        raise GithubOAuthStateError
    if not isinstance(payload.get('nonce'), str):
        raise GithubOAuthStateError


async def get_user_from_access_token(session: AsyncSession, token: str) -> User | None:
    """Resolve a JWT access token to a user."""
    try:
        user_id = decode_access_token(token)
    except JwtDecodeError:
        return None

    return await get_user_by_id(session, user_id)


async def authenticate_with_github(
    *,
    session: AsyncSession,
    code: str,
    redirect_uri: str,
) -> User:
    """Resolve the GitHub callback into a local user."""
    github_auth_config = get_settings().auth.github
    if not github_auth_config:
        raise GithubOAuthConfigurationError

    timeout = aiohttp.ClientTimeout(total=GITHUB_HTTP_TIMEOUT_SECONDS)
    async with aiohttp.ClientSession(timeout=timeout) as client:
        access_token = await _exchange_github_code_for_access_token(
            client,
            github_auth_config,
            code,
            redirect_uri,
        )
        identity = await _fetch_github_identity(
            client=client,
            access_token=access_token,
        )
    user_by_github = await get_user_by_github_user_id(session, identity.github_user_id)
    if user_by_github is not None:
        if user_by_github.github_username != identity.github_username:
            return await update_user_github_identity(
                session,
                user=user_by_github,
                github_user_id=identity.github_user_id,
                github_username=identity.github_username,
            )
        return user_by_github

    user_by_login = await get_user_by_login(session, identity.email)
    if user_by_login is not None:
        if user_by_login.github_user_id is not None and user_by_login.github_user_id != identity.github_user_id:
            raise GithubOAuthError('This email is already linked to a different GitHub account.')
        return await update_user_github_identity(
            session,
            user=user_by_login,
            github_user_id=identity.github_user_id,
            github_username=identity.github_username,
        )

    return await create_user(
        session,
        login=identity.email,
        password_hash=_generate_unusable_password_hash(),
        github_user_id=identity.github_user_id,
        github_username=identity.github_username,
    )


def _generate_unusable_password_hash() -> str:
    """Create a random password hash for accounts created via OAuth."""
    return hash_password(secrets.token_urlsafe(48))


async def _exchange_github_code_for_access_token(
    client: aiohttp.ClientSession,
    github_auth_config: GithubAuthConfig,
    code: str,
    redirect_uri: str,
) -> str:
    response = await _send_github_request(
        client=client,
        url=GITHUB_ACCESS_TOKEN_URL,
        form_data={
            'client_id': github_auth_config.client_id,
            'client_secret': github_auth_config.client_secret,
            'code': code,
            'redirect_uri': redirect_uri,
        },
    )
    access_token = response.get('access_token')
    if not isinstance(access_token, str) or not access_token:
        raise GithubOAuthError('GitHub did not return an access token.')
    return access_token


async def _fetch_github_identity(
    *,
    client: aiohttp.ClientSession,
    access_token: str,
) -> GithubIdentity:
    profile_data, email_data = await asyncio.gather(
        _send_github_request(client=client, url=GITHUB_USER_URL, access_token=access_token),
        _send_github_request(client=client, url=GITHUB_EMAILS_URL, access_token=access_token),
    )

    github_user_id = profile_data.get('id')
    github_username = profile_data.get('login')
    if not isinstance(github_user_id, int) or not isinstance(github_username, str) or not github_username:
        raise GithubOAuthError('GitHub did not return a valid user profile.')

    email = _extract_primary_email(email_data)
    return GithubIdentity(
        github_user_id=github_user_id,
        github_username=github_username,
        email=email,
    )


def _extract_primary_email(payload: object) -> str:
    if not isinstance(payload, list):
        raise GithubOAuthError('GitHub returned an unexpected email response.')

    selected_email = _select_github_email(payload)
    if selected_email is None:
        raise GithubEmailNotAvailableError
    return selected_email


def _select_github_email(payload: list[object]) -> str | None:
    selected_email: str | None = None
    for item in payload:
        email = _extract_verified_email(item)
        if email is None:
            continue

        if _is_primary_email(item):
            return email
        if selected_email is None:
            selected_email = email

    return selected_email


def _extract_verified_email(item: object) -> str | None:
    if not isinstance(item, dict):
        return None

    email = item.get('email')
    verified = item.get('verified')
    if not isinstance(email, str) or not email or verified is not True:
        return None
    return email


def _is_primary_email(item: object) -> bool:
    return isinstance(item, dict) and item.get('primary') is True


async def _send_github_request(
    *,
    client: aiohttp.ClientSession,
    url: str,
    form_data: dict[str, str] | None = None,
    access_token: str | None = None,
) -> dict[str, object] | list[object]:
    headers = _build_github_headers(access_token)

    try:
        request_context = _build_github_request_context(
            client=client,
            url=url,
            form_data=form_data,
            headers=headers,
        )
        async with request_context as response:
            parsed_payload = await _parse_github_response(response)
            if response.status >= 400:
                raise GithubOAuthError(_extract_github_error_message(parsed_payload))
    except (TimeoutError, aiohttp.ClientError) as error:
        raise GithubOAuthError('Could not reach GitHub during sign-in.') from error

    if isinstance(parsed_payload, dict) and isinstance(parsed_payload.get('error'), str):
        error_description = parsed_payload.get('error_description')
        if isinstance(error_description, str) and error_description:
            raise GithubOAuthError(error_description)
        raise GithubOAuthError(str(parsed_payload['error']))

    if not isinstance(parsed_payload, (dict, list)):
        raise GithubOAuthError('GitHub returned an unexpected payload.')

    return parsed_payload


def _build_github_headers(access_token: str | None) -> dict[str, str]:
    headers = {
        'Accept': 'application/json',
        'User-Agent': 'wad-2026-llm-chat',
    }
    if access_token is None:
        return headers

    headers['Accept'] = 'application/vnd.github+json'
    headers['Authorization'] = f'Bearer {access_token}'
    headers['X-GitHub-Api-Version'] = '2022-11-28'
    return headers


def _build_github_request_context(
    *,
    client: aiohttp.ClientSession,
    url: str,
    form_data: dict[str, str] | None,
    headers: dict[str, str],
) -> aiohttp.client._BaseRequestContextManager[aiohttp.ClientResponse]:
    if form_data is not None:
        return client.post(url, data=form_data, headers=headers)
    return client.get(url, headers=headers)


async def _parse_github_response(response: aiohttp.ClientResponse) -> dict[str, object] | list[object]:
    try:
        payload = await response.json(content_type=None)
    except (aiohttp.ContentTypeError, ValueError):
        raw_payload = await response.text()
        if raw_payload:
            raise GithubOAuthError(raw_payload) from None
        raise GithubOAuthError('GitHub returned an unreadable response.') from None

    if not isinstance(payload, (dict, list)):
        raise GithubOAuthError('GitHub returned an unexpected payload.')
    return payload


def _extract_github_error_message(payload: dict[str, object] | list[object]) -> str:
    if isinstance(payload, dict):
        message = payload.get('error_description') or payload.get('message') or payload.get('error')
        if isinstance(message, str) and message:
            return message
    return 'GitHub rejected the sign-in request.'
