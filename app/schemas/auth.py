from pydantic import BaseModel, EmailStr, Field


class RegisterRequest(BaseModel):
    """Registration request payload."""

    login: EmailStr
    password: str = Field(min_length=6, max_length=128)


class LoginRequest(BaseModel):
    """Login request payload."""

    login: EmailStr
    password: str


class TokenPair(BaseModel):
    """JWT access token plus Redis-backed refresh token."""

    access_token: str
    refresh_token: str
    token_type: str = 'bearer'
