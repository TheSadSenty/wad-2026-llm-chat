# wad-2026-llm-chat

Server-rendered LLM chat application built with FastAPI, PostgreSQL, and a local GGUF model.

## Requirements

- Python `3.13`
- [`uv`](https://docs.astral.sh/uv/)
- Docker and Docker Compose
- A local GGUF model file, for example [`qwen.gguf`](./qwen.gguf)

## Configuration

The application loads configuration from the project-level `.env` file.

1. Copy the example file:

```shell
cp .env.example .env
```

2. Fill in the required secrets, especially:

- `LLM_CHAT_AUTH__JWT_SECRET`
- `LLM_CHAT_DATABASE__POSTGRES__USER`
- `LLM_CHAT_DATABASE__POSTGRES__PASSWORD`

All variables use the `LLM_CHAT_` prefix and nested sections use `__`.

Example:

```env
LLM_CHAT_DATABASE__POSTGRES__PORT=6432
LLM_CHAT_LLM__GGUF_PATH=/absolute/path/to/model.gguf
```

## Local Python Setup With `uv`

Create the local virtual environment and sync dependencies:

```shell
uv sync
```

This creates `.venv` if it does not exist and installs the locked default dependencies.

If you also want the optional groups used in this repository:

```shell
uv sync --group linters --group tests
```

Activate the environment if you want a regular shell session inside it:

```shell
source .venv/bin/activate
```

## Run Locally With `uv` And Compose-Managed PostgreSQL

If you want to run the FastAPI app from your local `.venv` but do not want to install PostgreSQL on the host, you can start only the database-related Compose services.

1. Create and fill `.env`:

```shell
cp .env.example .env
```

2. Start PostgreSQL and run migrations in containers:

```shell
docker compose up db prestart
```

3. Start the app from the host:

```shell
uv run python -m app
```

With the default `.env.example` values, the host app connects to PostgreSQL at `127.0.0.1:5432`, while Docker Compose provides the actual database container.

Use this mode when you want:

- PostgreSQL from Docker
- Alembic migrations from Docker
- FastAPI app from the local `uv` environment

## Run Locally Without Docker

1. Make sure PostgreSQL is running locally and `.env` points to it.
2. Apply migrations:

```shell
uv run alembic upgrade head
```

3. Start the app:

```shell
uv run python -m app
```

The app listens on `http://127.0.0.1:8000` with the default example config in both local `uv` workflows.

## Run Locally With Docker Compose

The repository includes a local `docker-compose.yml` for the backend and PostgreSQL.

1. Create and fill `.env`:

```shell
cp .env.example .env
```

2. Start the stack:

```shell
docker compose up --build
```

Compose uses the same project-level `.env` file.

This starts:

- `backend` on `http://localhost:8000`
- `db` on `localhost:5432`

The `prestart` container runs `alembic upgrade head` before the backend starts.

Notes:

- Inside Docker Compose, the application connects to PostgreSQL via the service name `db`.
- The compose file overrides `LLM_CHAT_DATABASE__POSTGRES__HOST=db` automatically for the app containers.
- The image copies `qwen.gguf` into the container, so the default `LLM_CHAT_LLM__GGUF_PATH=./qwen.gguf` works there too.

## Available Configuration Options

All available settings currently come from [`app/config.py`](./app/config.py).

| Variable | Required | Default in `.env.example` | Description |
| --- | --- | --- | --- |
| `LLM_CHAT_APP__HOST` | No | `127.0.0.1` | Host interface used by Uvicorn. |
| `LLM_CHAT_APP__PORT` | No | `8000` | Port used by Uvicorn. |
| `LLM_CHAT_AUTH__JWT_SECRET` | Yes | none | Secret used to sign and verify JWT tokens and GitHub OAuth state tokens. |
| `LLM_CHAT_AUTH__ACCESS_TOKEN_TTL_MINUTES` | No | `60` | Access token lifetime in minutes. |
| `LLM_CHAT_AUTH__GITHUB__CLIENT_ID` | No | none | GitHub OAuth app client ID. Required only when enabling GitHub sign-in. |
| `LLM_CHAT_AUTH__GITHUB__CLIENT_SECRET` | No | none | GitHub OAuth app client secret. Required only when enabling GitHub sign-in. |
| `LLM_CHAT_AUTH__GITHUB__ALLOW_SIGNUP` | No | `true` when set | Controls GitHub's signup prompt in the authorization flow. Only used when GitHub OAuth config is present. |
| `LLM_CHAT_DATABASE__POSTGRES__HOST` | No | `127.0.0.1` | PostgreSQL host. In Docker Compose this is overridden to `db` for app containers. |
| `LLM_CHAT_DATABASE__POSTGRES__PORT` | No | `5432` | PostgreSQL port. |
| `LLM_CHAT_DATABASE__POSTGRES__DBNAME` | No | `llm-chat` | PostgreSQL database name. |
| `LLM_CHAT_DATABASE__POSTGRES__USER` | Yes | none | PostgreSQL username. |
| `LLM_CHAT_DATABASE__POSTGRES__PASSWORD` | Yes | none | PostgreSQL password. |
| `LLM_CHAT_LLM__GGUF_PATH` | Yes | `./qwen.gguf` | Path to the local GGUF model file used by `llama-cpp-python`. |

## GitHub OAuth

GitHub OAuth is optional. To enable it, set:

- `LLM_CHAT_AUTH__GITHUB__CLIENT_ID`
- `LLM_CHAT_AUTH__GITHUB__CLIENT_SECRET`

You can also set:

- `LLM_CHAT_AUTH__GITHUB__ALLOW_SIGNUP=true`

Register the callback URL on your GitHub OAuth app as:

```text
/auth/github/callback
```
