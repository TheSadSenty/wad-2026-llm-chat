import uvicorn
from fastapi import FastAPI

from app.config import get_settings
from app.controllers.auth import auth_router
from app.controllers.chat import chat_router


def create_app(*, init_database: bool = True) -> FastAPI:
    """Create and configure the FastAPI application."""
    del init_database
    application = FastAPI(title='wad-2026-llm-chat')
    application.include_router(auth_router)
    application.include_router(chat_router)
    return application


def main(host: str | None = None, port: int | None = None, *, init_database: bool = True) -> None:
    """Run the application with Uvicorn."""
    settings = get_settings()
    application = create_app(init_database=init_database)
    uvicorn.run(
        application,
        host=host or settings.app.host,
        port=port or settings.app.port,
        reload=False,
    )


if __name__ == '__main__':
    settings = get_settings()
    main(host=settings.app.host, port=settings.app.port)
