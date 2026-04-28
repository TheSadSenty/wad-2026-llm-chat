from typing import override

from fastapi import FastAPI, Request
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response

from app.db import SessionLocal
from app.services.auth import get_access_token_from_request, get_user_from_access_token


class AuthMiddleware(BaseHTTPMiddleware):
    """Attach the authenticated user to request state."""

    @override
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        """Process user request and return responses.

        Args:
            request: User request.
            call_next: Func to get response for request.

        Returns:
            HTTP responses.

        """
        request.state.current_user = None
        token = get_access_token_from_request(request)
        if token is not None:
            async with SessionLocal() as session:
                request.state.current_user = await get_user_from_access_token(session, token)

        return await call_next(request)


def register_auth_middleware(application: FastAPI) -> None:
    """Register middleware that resolves the authenticated user from JWT."""
    application.add_middleware(AuthMiddleware)
