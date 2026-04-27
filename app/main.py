from fastapi import FastAPI

from app.controllers.auth import auth_router


def create_app(*, init_database: bool = True) -> FastAPI:
    """Create and configure the FastAPI application."""
    del init_database
    application = FastAPI(title='wad-2026-llm-chat')
    application.include_router(auth_router)
    return application
