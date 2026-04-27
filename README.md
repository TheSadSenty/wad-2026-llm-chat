# wad-2026-llm-chat

## Database and migrations

The application uses PostgreSQL and loads settings from `config.toml`.

- Default database URL: `postgresql+psycopg://postgres:changethis@127.0.0.1:5432/llm-chat`
- Local model path: `./model.gguf`
- Environment variables with the `LLM_CHAT_` prefix override TOML values.
- Example override: `LLM_CHAT_DATABASE__POSTGRES__PORT=6432`
- Example override: `LLM_CHAT_LLM__GGUF_PATH=/absolute/path/to/model.gguf`
- Run migrations: `uv run alembic upgrade head`

## Production docker compose

Start the production stack with:

```shell
docker compose up --build
```

This brings up:

- `app` on `http://localhost:8000`
- `postgres` on `localhost:5432`

The application container applies Alembic migrations before starting FastAPI.
