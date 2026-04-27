# Tools and MCP servers

- Always use Context7 when I need library/API documentation, code generation, setup or configuration steps without me having to explicitly ask.
- For any file search or grep in the current git-indexed directory, use fff tools.

# Project technical specification

This document describes the requirements for the developing project.

## Core feature: LLM chat (ChatGPT-like)

Chat experience similar in spirit to OpenAI ChatGPT:

- Users can **create chats** (conversation threads).
- Within each chat, **request/response history** is persisted.
- Inside a chat, users can **ask the LLM questions** and receive answers.

## Architecture

- UI approach - **Server-rendered HTML** (templates generated on the backend)
- Required architecture - **MVC — Model–View–Controller** (models, views/templates, controllers).

## Backend Tech Stack

- Python
- FastAPI
- PostgreSQL
- Alembic for database migration
- JWT (access/refresh token flow)
- Redis

## Frontend Tech Stack

- HTMX

## Technical details

- LLM provided locally via gguf file
- It's preferred to use streaming for LLM answers
- Since it's Server-rendered app endpoints fill return HTML rather that JSON but should be accessible via JWT token, not classic session mechanism
- login would be a valid email address, but right now no need to check if this mail is exist


## Authentication and security

- **Registration** with **login + password**; **login must be unique**.
- **Passwords** must be stored **hashed** in the database. Use argon2
- Expose an **HTTP API** protected with **JWT** (access tokens).
- **Refresh sessions** (refresh tokens or equivalent session records) must be stored in **Redis** with a **TTL of 30 days**.

## API

- REST (or similar) API built with **FastAPI**.
- Endpoints for auth, chats, messages, and LLM interaction as appropriate for your design.
- JWT validation on protected routes.

# Folder structure

`./backend/` - Folder with FastAPI backend code
`./backend/__main__.py` - FastAPI backend entrypoint

# How to run project

To run project use command:

```shell
uv run python -m app
```

# How to run tests

- To run tests use command:

```shell
make unit
```

- To run tests with coverage use command:

```shell
make unit_cov
```

- Don't run tests unless user explicitly says that

# How to run linters

- To run flake8(wemake-python-styleguide) linter use command:

```shell
make flake8
```

- To run mypy type-checker use command:

```shell
make mypy
```

- To run ruff linter and ruff format checker use command:

```shell
make ruff
```

- To run all linters at once use command:

```shell
make linters
```

- Don't run any linters unless user explicitly says that

# Code style&formatting

- To run code formatting use command:

```shell
make ruff_formatter
```

Try to follow that rules instead of running code formatting:
  - Use single quotes for strings and double quotes for docstring
  - Max line length is 120 symbols
  - Use [rules](https://wemake-python-styleguide.readthedocs.io/en/latest/pages/usage/violations/index.html) from wemake-python-styleguide linter

- Don't run code formatter unless user explicitly says that

# How to add dependencies

- To run all linters at once use command:

```shell
uv add <dependency_name>
```

- Don't add dependencies unless user explicitly says that
