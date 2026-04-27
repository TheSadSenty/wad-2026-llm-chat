import uvicorn

from app.config import get_settings
from app.main import create_app


def main(host: str | None = None, port: int | None = None, *, init_database: bool = True) -> None:
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
