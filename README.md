# wad-2026-llm-chat

Server-rendered LLM chat application built with FastAPI, PostgreSQL, Redis, and a local GGUF model.

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

If you want to run the FastAPI app from your local `.venv` but do not want to install PostgreSQL or Redis on the host, you can start only the required Compose services.

1. Create and fill `.env`:

```shell
cp .env.example .env
```

2. Start PostgreSQL, Redis, and run migrations in containers:

```shell
docker compose up db redis prestart
```

3. Start the app from the host:

```shell
uv run python -m app
```

With the default `.env.example` values, the host app connects to PostgreSQL at `127.0.0.1:5432` and Redis at `127.0.0.1:6379`, while Docker Compose provides the actual containers.

Use this mode when you want:

- PostgreSQL from Docker
- Redis from Docker
- Alembic migrations from Docker
- FastAPI app from the local `uv` environment

## Run Locally Without Docker

1. Make sure PostgreSQL and Redis are running locally and `.env` points to them.
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

The repository includes a local `docker-compose.yml` for the backend, PostgreSQL, and Redis.

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
- `redis` on `localhost:6379`

The `prestart` container runs `alembic upgrade head` before the backend starts.

Notes:

- Inside Docker Compose, the application connects to PostgreSQL via the service name `db`.
- Inside Docker Compose, the application connects to Redis via the service name `redis`.
- The compose file overrides `LLM_CHAT_DATABASE__POSTGRES__HOST=db` automatically for the app containers.
- The compose file overrides `LLM_CHAT_REDIS__HOST=redis` automatically for the app container.
- The image copies `qwen.gguf` into the container, so the default `LLM_CHAT_LLM__GGUF_PATH=./qwen.gguf` works there too.

## Authentication API

Authentication is now token-based.

- `POST /api/auth/register` returns an access token and refresh token.
- `POST /api/auth/login` returns an access token and refresh token.
- `POST /api/auth/refresh?refresh_token=...` rotates the refresh token and returns a new pair.
- `POST /api/auth/logout?refresh_token=...` invalidates the refresh session in Redis.
- `GET /api/auth/github/login` starts GitHub OAuth.
- `GET /api/auth/github/callback` completes GitHub OAuth and redirects with the token pair in query parameters.

Protected requests should send:

```text
Authorization: Bearer <access_token>
```

## Available Configuration Options

All available settings currently come from [`app/config.py`](./app/config.py).

| Variable | Required | Default in `.env.example` | Description |
| --- | --- | --- | --- |
| `LLM_CHAT_APP__HOST` | No | `127.0.0.1` | Host interface used by Uvicorn. |
| `LLM_CHAT_APP__PORT` | No | `8000` | Port used by Uvicorn. |
| `LLM_CHAT_AUTH__JWT_SECRET` | Yes | none | Secret used to sign and verify JWT tokens and GitHub OAuth state tokens. |
| `LLM_CHAT_AUTH__ACCESS_TOKEN_TTL_MINUTES` | No | `60` | Access token lifetime in minutes. |
| `LLM_CHAT_AUTH__REFRESH_TOKEN_TTL_DAYS` | No | `30` | Refresh-session lifetime in Redis, in days. |
| `LLM_CHAT_AUTH__GITHUB__CLIENT_ID` | No | none | GitHub OAuth app client ID. Required only when enabling GitHub sign-in. |
| `LLM_CHAT_AUTH__GITHUB__CLIENT_SECRET` | No | none | GitHub OAuth app client secret. Required only when enabling GitHub sign-in. |
| `LLM_CHAT_AUTH__GITHUB__ALLOW_SIGNUP` | No | `true` when set | Controls GitHub's signup prompt in the authorization flow. Only used when GitHub OAuth config is present. |
| `LLM_CHAT_DATABASE__POSTGRES__HOST` | No | `127.0.0.1` | PostgreSQL host. In Docker Compose this is overridden to `db` for app containers. |
| `LLM_CHAT_DATABASE__POSTGRES__PORT` | No | `5432` | PostgreSQL port. |
| `LLM_CHAT_DATABASE__POSTGRES__DBNAME` | No | `llm-chat` | PostgreSQL database name. |
| `LLM_CHAT_DATABASE__POSTGRES__USER` | Yes | none | PostgreSQL username. |
| `LLM_CHAT_DATABASE__POSTGRES__PASSWORD` | Yes | none | PostgreSQL password. |
| `LLM_CHAT_REDIS__HOST` | No | `127.0.0.1` | Redis host. In Docker Compose this is overridden to `redis` for the app container. |
| `LLM_CHAT_REDIS__PORT` | No | `6379` | Redis port. |
| `LLM_CHAT_REDIS__DB` | No | `0` | Redis database index used for refresh-session storage. |
| `LLM_CHAT_REDIS__PASSWORD` | No | none | Optional Redis password. |
| `LLM_CHAT_LLM__GGUF_PATH` | Yes | `./qwen.gguf` | Path to the local GGUF model file used by `llama-cpp-python`. |

## GitHub OAuth

GitHub OAuth is optional. To enable it, set:

- `LLM_CHAT_AUTH__GITHUB__CLIENT_ID`
- `LLM_CHAT_AUTH__GITHUB__CLIENT_SECRET`

You can also set:

- `LLM_CHAT_AUTH__GITHUB__ALLOW_SIGNUP=true`

Register the callback URL on your GitHub OAuth app as:

```text
/api/auth/github/callback
```
