# syntax=docker/dockerfile:1.7

# --- Builder stage: resolve and install deps into a venv with uv ---
FROM python:3.12-slim AS builder

# Pull a known uv binary; pinning to a tag keeps builds reproducible.
COPY --from=ghcr.io/astral-sh/uv:0.5.18 /uv /uvx /usr/local/bin/

ENV UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1 \
    UV_PYTHON_DOWNLOADS=never \
    UV_PROJECT_ENVIRONMENT=/opt/venv

WORKDIR /app

# Install dependencies first (cached layer) — only pyproject + lockfile, no source.
COPY pyproject.toml uv.lock README.md ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-install-project --no-dev --no-editable

# Now install the project itself (non-editable so the venv is self-contained).
COPY src ./src
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-editable

# --- Runtime stage: copy the prebuilt venv onto a slim base ---
FROM python:3.12-slim AS runtime

# Run as non-root.
RUN groupadd --system --gid 1000 app \
    && useradd --system --uid 1000 --gid app --home /home/app --create-home app

COPY --from=builder /opt/venv /opt/venv

ENV PATH=/opt/venv/bin:$PATH \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

USER app
WORKDIR /home/app

EXPOSE 8000

# Defaults to stdio. Override at `docker run` time for http:
#   docker run -e SUPERPOSITION_ENDPOINT=... -p 8000:8000 IMAGE \
#     --transport http --host 0.0.0.0 --port 8000
ENTRYPOINT ["superposition-mcp"]
