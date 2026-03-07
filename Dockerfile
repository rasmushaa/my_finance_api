FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc curl && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

# Copy everything needed for dependencies first (better layer caching)
COPY pyproject.toml uv.lock /app/

# Accept build arguments for private registry authentication
ARG GOOGLE_OAUTH_ACCESS_TOKEN
ARG GCP_LOCATION
ARG GCP_PROJECT_ID

# Use uv workspace mode to install with frozen dependencies from uv.lock to system Python env
# Configure authentication for private Artifact Registry if token is provided
RUN uv venv --system && \
    if [ -n "$GOOGLE_OAUTH_ACCESS_TOKEN" ]; then \
        uv sync --frozen --extra-index-url https://oauth2accesstoken:${GOOGLE_OAUTH_ACCESS_TOKEN}@${GCP_LOCATION}-python.pkg.dev/${GCP_PROJECT_ID}/python-packages/simple/; \
    else \
        uv sync --frozen; \
    fi

# Copy application code
COPY app /app/app/

# Copy model artifacts (assumed to be pre-loaded by CI/CD pipeline, NOT from local ./model_artifacts!)
COPY model_artifacts /app/model_artifacts/

# Runtime environment (set by deployment context)
ARG ENV=dev
ENV ENV=$ENV

# Create non-root user for security (Cloud Run best practice)
RUN useradd --create-home --shell /bin/bash app \
    && chown -R app:app /app
USER app

# Use environment variable for port (Cloud Run requirement)
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8080}"]
