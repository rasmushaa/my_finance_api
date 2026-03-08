# syntax=docker/dockerfile:1.7
FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc curl \
    && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

ARG ENV=dev
ENV ENV=${ENV}

# Keep the project virtualenv inside the app directory
ENV UV_PROJECT_ENVIRONMENT=/app/.venv
ENV PATH="/app/.venv/bin:${PATH}"

# Copy dependency metadata first for better caching
COPY pyproject.toml /app/
COPY README* /app/

# Copy lockfile too if you use one
COPY uv.lock* /app/

# Install only dependencies first, not the local project itself
# The index is already defined in pyproject.toml as "private"
RUN --mount=type=secret,id=oauth_token \
    --mount=type=cache,target=/root/.cache/uv \
    set -eux; \
    TOKEN="$(cat /run/secrets/oauth_token)"; \
    export UV_INDEX_PRIVATE_USERNAME="oauth2accesstoken"; \
    export UV_INDEX_PRIVATE_PASSWORD="${TOKEN}"; \
    uv sync --no-dev --no-install-project

# Now copy the application code and artifacts
COPY app /app/app/
COPY model_artifacts /app/model_artifacts/

RUN useradd --create-home --shell /bin/bash appuser \
    && chown -R appuser:appuser /app

USER appuser

EXPOSE 8080

CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8080}"]
