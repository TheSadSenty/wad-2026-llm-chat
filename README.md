# wad-2026-llm-chat

Server-rendered LLM chat application built with FastAPI, PostgreSQL, Redis, and a local GGUF model.

## Current Stack

- Python `3.13`
- FastAPI
- SQLAlchemy + Alembic
- PostgreSQL
- Redis
- JWT access tokens
- `llama-cpp-python` with a local GGUF model

## Requirements

- Python `3.13`
- [`uv`](https://docs.astral.sh/uv/)
- Docker and Docker Compose if you want containerized PostgreSQL and Redis
- A local GGUF model file, for example [`qwen.gguf`](./qwen.gguf)

## Configuration

The application loads configuration from the project-level `.env` file.

1. Copy the example file:

```shell
cp .env.example .env
```

2. Fill in the required values:

- `LLM_CHAT_AUTH__JWT_SECRET`
- `LLM_CHAT_DATABASE__POSTGRES__USER`
- `LLM_CHAT_DATABASE__POSTGRES__PASSWORD`
- `LLM_CHAT_LLM__GGUF_PATH` if your model is not at `./qwen.gguf`

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

If you also want the optional dependency groups used by this repository:

```shell
uv sync --group linters --group tests
```

Activate the environment if you want an interactive shell inside it:

```shell
source .venv/bin/activate
```

## Run Locally With `uv` And Compose-Managed Services

Use this mode when you want the app to run from your host environment but PostgreSQL, Redis, and migrations to run in Docker.

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

With the default `.env.example`, the host app connects to PostgreSQL at `127.0.0.1:5432` and Redis at `127.0.0.1:6379`.

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

With the default example config, the app listens on `http://127.0.0.1:8000`.

## Run Locally With Docker Compose

The repository includes a `docker-compose.yml` for the backend, PostgreSQL, Redis, and a prestart migration job.

1. Create and fill `.env`:

```shell
cp .env.example .env
```

2. Start the stack:

```shell
docker compose up --build
```

This starts:

- `backend` on `http://localhost:8000`
- `db` on `localhost:5432`
- `redis` on `localhost:6379`

Notes:

- The `prestart` service runs `alembic upgrade head` before the backend starts.
- Inside Compose, the app connects to PostgreSQL via `db` and Redis via `redis`.
- The image copies `qwen.gguf` into the container, so `LLM_CHAT_LLM__GGUF_PATH=./qwen.gguf` works there if that file exists in the project root during build.

## Authentication Model

Authentication is token-based.

- `POST /api/auth/register` accepts JSON and returns an access token plus refresh token.
- `POST /api/auth/login` accepts JSON and returns an access token plus refresh token.
- `POST /api/auth/refresh?refresh_token=...` rotates the refresh token and returns a fresh pair.
- `POST /api/auth/logout?refresh_token=...` deletes the refresh session from Redis.
- `GET /api/auth/github/login` starts GitHub OAuth.
- `GET /api/auth/github/callback` completes GitHub OAuth.

Protected endpoints expect:

```text
Authorization: Bearer <access_token>
```

Refresh sessions are stored in Redis with TTL based on `LLM_CHAT_AUTH__REFRESH_TOKEN_TTL_DAYS`.

## Browser Flow

The app does not use cookie-based sessions for the chat UI.

- `/login` renders the login page
- `/register` renders the registration page
- `/chats` renders the chat workspace

The browser pages use JavaScript to:

- call the auth API
- store `access_token` and `refresh_token` in `localStorage`
- send the access token as a Bearer token on chat requests
- call refresh/logout endpoints with the refresh token

## Chat Endpoints

The chat UI is server-rendered HTML, but authenticated with JWT Bearer tokens.

- `GET /` redirects to `/chats`
- `GET /chats` renders the chat page for the current user
- `POST /chats` creates a new chat and redirects to it
- `POST /chats/{chat_id}/messages` appends a message and redirects back to the chat

Streaming endpoints are also available and used by the browser UI:

- `POST /chats/stream` creates a new chat and streams the assistant reply
- `POST /chats/{chat_id}/messages/stream` appends a message and streams the assistant reply

Streaming responses use Server-Sent Events with `meta`, `token`, `done`, and `error` events.

## Available Configuration Options

All runtime settings come from [`app/config.py`](./app/config.py).

| Variable | Required | Default in `.env.example` | Description |
| --- | --- | --- | --- |
| `LLM_CHAT_APP__HOST` | No | `127.0.0.1` | Host interface used by Uvicorn. |
| `LLM_CHAT_APP__PORT` | No | `8000` | Port used by Uvicorn. |
| `LLM_CHAT_AUTH__JWT_SECRET` | Yes | none | Secret used to sign and verify JWT tokens and GitHub OAuth state tokens. |
| `LLM_CHAT_AUTH__ACCESS_TOKEN_TTL_MINUTES` | No | `60` | Access token lifetime in minutes. |
| `LLM_CHAT_AUTH__REFRESH_TOKEN_TTL_DAYS` | No | `30` | Refresh-session lifetime in Redis, in days. |
| `LLM_CHAT_AUTH__GITHUB__CLIENT_ID` | No | none | GitHub OAuth app client ID. Required only when enabling GitHub sign-in. |
| `LLM_CHAT_AUTH__GITHUB__CLIENT_SECRET` | No | none | GitHub OAuth app client secret. Required only when enabling GitHub sign-in. |
| `LLM_CHAT_AUTH__GITHUB__ALLOW_SIGNUP` | No | none | Controls GitHub's signup prompt in the authorization flow when GitHub OAuth is enabled. |
| `LLM_CHAT_DATABASE__POSTGRES__HOST` | No | `127.0.0.1` | PostgreSQL host. In Docker Compose this is overridden to `db` for app containers. |
| `LLM_CHAT_DATABASE__POSTGRES__PORT` | No | `5432` | PostgreSQL port. |
| `LLM_CHAT_DATABASE__POSTGRES__DBNAME` | No | `llm-chat` | PostgreSQL database name. |
| `LLM_CHAT_DATABASE__POSTGRES__USER` | Yes | none | PostgreSQL username. |
| `LLM_CHAT_DATABASE__POSTGRES__PASSWORD` | Yes | none | PostgreSQL password. |
| `LLM_CHAT_REDIS__HOST` | No | `127.0.0.1` | Redis host. In Docker Compose this is overridden to `redis`. |
| `LLM_CHAT_REDIS__PORT` | No | `6379` | Redis port. |
| `LLM_CHAT_REDIS__DB` | No | `0` | Redis database index used for refresh sessions. |
| `LLM_CHAT_REDIS__PASSWORD` | No | none | Optional Redis password. |
| `LLM_CHAT_LLM__GGUF_PATH` | Yes | `./qwen.gguf` | Path to the local GGUF model file used by `llama-cpp-python`. |

## GitHub OAuth

GitHub OAuth is optional. To enable it, set:

- `LLM_CHAT_AUTH__GITHUB__CLIENT_ID`
- `LLM_CHAT_AUTH__GITHUB__CLIENT_SECRET`

Optional:

- `LLM_CHAT_AUTH__GITHUB__ALLOW_SIGNUP=true`

Register the callback URL on your GitHub OAuth app as the full URL to:

```text
/api/auth/github/callback
```
