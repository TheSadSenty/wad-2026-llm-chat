from pydantic import BaseModel, EmailStr


class LoginForm(BaseModel):
    """Login payload parsed from the form body."""

    login: EmailStr
    password: str


class RegistrationForm(BaseModel):
    """Registration payload parsed from the form body."""

    login: EmailStr
    password: str
