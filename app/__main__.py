import uvicorn
from fastapi import FastAPI

from app.config import get_settings
from app.controllers.auth import auth_pages_router, auth_router
from app.controllers.chat import chat_router


def create_app(*, init_database: bool = True) -> FastAPI:
    application = FastAPI(title='WAD 2026 LLM Chat')
    application.state.init_database = init_database
    application.include_router(auth_pages_router)
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
