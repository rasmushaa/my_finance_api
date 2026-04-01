# My Finance API

FastAPI backend for personal finance ingestion and ML-assisted transaction categorization.

This is a hobby project deployed publicly on Google Cloud Run. The codebase follows pragmatic architecture patterns (DI container, typed settings, explicit schemas) without claiming full enterprise production hardening.

[![Swagger](https://img.shields.io/badge/Swagger-Docs-blue.svg)](https://my-finance-api-prod-109245832287.europe-north1.run.app/docs)
[![CI](https://github.com/rasmushaa/my_finance_api/actions/workflows/deploy.yml/badge.svg)](https://github.com/rasmushaa/my_finance_api/actions/workflows/deploy.yml)

## Tech Stack

- Python 3.11
- FastAPI + Pydantic
- Google BigQuery
- MLflow-managed model artifacts
- Dependency management with `uv`
- Testing with `pytest` + DuckDB-backed mock client

## Project Layout

```text
app/
  api/                # Routers and dependency providers
  core/               # DI container, db client, settings, security, errors
  schemas/            # Pydantic request/response contracts
  services/           # Business logic
config/
  bigquery_tables.yaml # BigQuery table schema source-of-truth
scripts/
  init_gbq_tables.py   # Creates BigQuery tables from YAML schema
  bigquery_table_config.py
  load_model_artifacts.py
tests/
  unit/
  integration/
  helpers/
```

## Architecture Notes

- Dependency wiring is centralized in `app/core/container.py`.
- Runtime settings are typed (`app/core/settings.py`) and loaded from env vars.
- API contracts live in `app/schemas/`.
- Domain and infrastructure errors are unified under `AppError` and mapped to consistent HTTP responses.
- BigQuery table schema is defined once in `config/bigquery_tables.yaml` and consumed by scripts/tests.

## BigQuery Schema Source-of-Truth

`config/bigquery_tables.yaml` is the canonical schema contract for:

1. Table initialization via `scripts/init_gbq_tables.py`
2. Test mock-table validation in `tests/helpers/duckdb_mock_client.py`

If a table schema changes, update this YAML first, then update service logic and tests.

## Local Development

### Prerequisites

- Python 3.11
- `uv`
- `gcloud` CLI authenticated for private package index and GCP access

### Install Dependencies

```bash
./scripts/uv_sync.sh
```

Alternative manual install:

```bash
TOKEN="$(gcloud auth print-access-token)"
uv sync --group dev \
  --extra-index-url "https://oauth2accesstoken:${TOKEN}@europe-north1-python.pkg.dev/rasmus-prod/python-packages/simple/"
```

### Environment Variables

Minimum runtime variables:

```bash
export APP_JWT_SECRET="your-jwt-secret"
export APP_JWT_EXP_DELTA_MINUTES="60"
export GOOGLE_OAUTH_CLIENT_ID="your-google-client-id"
export GOOGLE_OAUTH_CLIENT_SECRET="your-google-client-secret"
export GCP_BQ_DATASET="your_dataset_base"
export ENV="dev"
```

Optional but recommended:

```bash
export GCP_PROJECT_ID="your-gcp-project"
export GCP_LOCATION="europe-north1"
```

### Run API Locally

```bash
./scripts/run_local_terminal.sh
```

Or directly:

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Initialize BigQuery Tables

```bash
uv run python scripts/init_gbq_tables.py dev
```

Supported environments: `dev`, `stg`, `prod`.

## Testing

### Run Unit-Focused Suite (default in CI)

```bash
uv run pytest -m "not integration"
```

If private index auth blocks `uv run` in a local shell, use existing venv:

```bash
.venv/bin/pytest -m "not integration"
```

### Run Integration Tests

```bash
uv run pytest -m integration -s
```

## API Endpoints (v1)

Base prefix: `/app/v1`

- `GET /health/`
- `POST /auth/google/code`
- `POST /model/predict` (admin)
- `GET /model/metadata` (admin)
- `GET /transactions/labels` (user)
- `POST /transactions/transform` (user)
- `POST /transactions/upload` (user)
- `POST /transactions/register-filetype` (admin)
- `POST /transactions/delete-filetype` (admin)
- `POST /assets/upload` (user)

Interactive docs:

- Swagger: `/docs`
- ReDoc: `/redoc`

## CI/CD

Single GitHub Actions workflow (`.github/workflows/deploy.yml`):

- `main`: run tests + deploy Cloud Run (`prod`)
- `stg`: run tests + deploy Cloud Run (`stg`)
- `feature/*`: run tests only

## Documentation Conventions

- Python docstrings use NumPy style.
- Router endpoint docstrings use Markdown sections so Swagger descriptions stay readable.
- Keep docs aligned with actual code and schema contracts.
