import secrets
from datetime import UTC, datetime, timedelta

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

from app.config import get_settings

password_hasher = PasswordHasher()
JWT_ALGORITHM = 'HS256'
JWT_TOKEN_TYPE = 'access'  # noqa: S105


class JwtDecodeError(Exception):
    """Raised when a JWT cannot be decoded or validated."""


def create_access_token(*, user_id: int) -> str:
    """Create a signed JWT access token for the given user."""
    settings = get_settings()
    now = datetime.now(tz=UTC)
    expires_at = now + timedelta(minutes=settings.auth.access_token_ttl_minutes)
    payload = {
        'sub': str(user_id),
        'type': JWT_TOKEN_TYPE,
        'iat': now,
        'exp': expires_at,
    }
    return jwt.encode(payload, settings.auth.jwt_secret, algorithm=JWT_ALGORITHM)


def decode_access_token(token: str) -> int:
    """Decode a JWT access token and return the embedded user id."""
    settings = get_settings()
    try:
        payload = jwt.decode(token, settings.auth.jwt_secret, algorithms=[JWT_ALGORITHM])
    except (jwt.ExpiredSignatureError, jwt.InvalidTokenError) as error:
        raise JwtDecodeError from error

    subject = payload.get('sub')
    token_type = payload.get('type')
    if token_type != JWT_TOKEN_TYPE:
        raise JwtDecodeError
    if not isinstance(subject, str) or not subject.isdigit():
        raise JwtDecodeError

    return int(subject)


def hash_password(password: str) -> str:
    """Hash a plaintext password using Argon2."""
    return password_hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    """Verify a plaintext password against its hash."""
    try:
        return password_hasher.verify(password_hash, password)
    except VerifyMismatchError:
        return False


def make_refresh_token() -> str:
    """Generate a high-entropy opaque refresh token."""
    return secrets.token_urlsafe(48)
