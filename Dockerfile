FROM python:3.13.13-slim-trixie

ENV PYTHONUNBUFFERED=1

COPY --from=ghcr.io/astral-sh/uv:0.10.12 /uv /uvx /bin/


ARG DEBIAN_FRONTEND=noninteractive
RUN apt-get update &&\
  apt-get install -y --no-install-recommends build-essential &&\
  rm -rf /var/lib/apt/lists/*

# Compile bytecode
# Ref: https://docs.astral.sh/uv/guides/integration/docker/#compiling-bytecode
ENV UV_COMPILE_BYTECODE=1

# uv Cache
# Ref: https://docs.astral.sh/uv/guides/integration/docker/#caching
ENV UV_LINK_MODE=copy

WORKDIR /app/

COPY qwen.gguf ./

# Place executables in the environment at the front of the path
# Ref: https://docs.astral.sh/uv/guides/integration/docker/#using-the-environment
ENV PATH="/app/.venv/bin:$PATH"

# Install dependencies
# Ref: https://docs.astral.sh/uv/guides/integration/docker/#intermediate-layers
RUN --mount=type=cache,target=/root/.cache/uv \
  --mount=type=bind,source=uv.lock,target=uv.lock \
  --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
  uv sync --frozen --no-install-project

COPY pyproject.toml alembic.ini config.toml ./

# Sync the project
# Ref: https://docs.astral.sh/uv/guides/integration/docker/#intermediate-layers
RUN --mount=type=cache,target=/root/.cache/uv \
  --mount=type=bind,source=uv.lock,target=uv.lock \
  --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
  uv sync --frozen

COPY ./app ./app/

CMD ["uv", "run", "python", "-m", "app"]
