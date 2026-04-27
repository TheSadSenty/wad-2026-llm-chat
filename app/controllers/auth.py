from typing import Annotated

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session

from app.db import get_db_session
from app.services.auth import RegistrationConflictError, register_user

auth_router = APIRouter(tags=['auth'])
templates = Jinja2Templates(directory='app/templates')


class RegistrationForm(BaseModel):
    """Registration payload parsed from the form body."""

    login: EmailStr
    password: str


def _render_registration_page(
    request: Request,
    *,
    error_message: str | None = None,
    login: str = '',
    status_code: int = 200,
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


@auth_router.get('/register', response_class=HTMLResponse)
async def registration_form(request: Request) -> HTMLResponse:
    """Render the user registration form."""
    return _render_registration_page(request)


@auth_router.post('/register', response_class=HTMLResponse, status_code=201)
async def register(
    request: Request,
    data: Annotated[RegistrationForm, Form()],
    session: Annotated[Session, Depends(get_db_session)],
) -> HTMLResponse:
    """Register a new user account."""
    try:
        created_user = register_user(
            session=session,
            login=str(data.login),
            password=data.password,
        )
    except RegistrationConflictError:
        return _render_registration_page(
            request,
            error_message='A user with this email already exists.',
            login=str(data.login),
            status_code=409,
        )

    return templates.TemplateResponse(
        request=request,
        name='auth/register.html',
        context={
            'error_message': None,
            'login': '',
            'success_message': f'User {created_user.login} registered successfully.',
        },
        status_code=201,
    )
