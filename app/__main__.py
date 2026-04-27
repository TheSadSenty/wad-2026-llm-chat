import uvicorn
from fastapi import FastAPI

from app.config import get_settings
from app.controllers.auth import auth_router
from app.controllers.chat import chat_router
from app.middleware import register_auth_middleware


def create_app() -> FastAPI:
    application = FastAPI(title='WAD 2026 LLM Chat')
    register_auth_middleware(application)
    application.include_router(auth_router)
    application.include_router(chat_router)
    return application


def main() -> None:
    settings = get_settings()
    application = create_app()
    uvicorn.run(
        application,
        host=settings.app.host,
        port=settings.app.port,
    )


if __name__ == '__main__':
    main()
