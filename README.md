# My Finance API

<p align="center">
  <img src="https://capsule-render.vercel.app/api?type=waving&height=260&color=0:0f766e,45:0369a1,100:0f172a&text=My%20Finance%20API&fontColor=ffffff&fontSize=58&animation=fadeIn&fontAlignY=40&desc=FastAPI%20%7C%20BigQuery%20%7C%20MLflow%20for%20Transaction%20Intelligence&descAlignY=63" alt="My Finance API hero banner" />
</p>

A production-style FastAPI backend for personal finance ingestion, transaction normalization, prediction logging, and model tracebility on Google Cloud.

[![Swagger](https://img.shields.io/badge/Live%20API-Swagger-blue.svg)](https://my-finance-api-prod-109245832287.europe-north1.run.app/docs)
[![CI](https://github.com/rasmushaa/my_finance_api/actions/workflows/deploy.yml/badge.svg)](https://github.com/rasmushaa/my_finance_api/actions/workflows/deploy.yml)
[![Python](https://img.shields.io/badge/Python-3.11-3776AB.svg)](https://www.python.org/)
[![Framework](https://img.shields.io/badge/FastAPI-Backend-009688.svg)](https://fastapi.tiangolo.com/)

## Project snapshot

- Problem: ingest bank CSV exports with varying schemas, normalize into a canonical format, run model inference, and persist both facts and prediction metadata.
- Architecture: layered FastAPI application (`api -> services -> core`) with explicit dependency wiring in a lightweight container.
- Data platform: BigQuery for primary storage, Cloud Storage for model artifacts and manifest, MLflow-compatible model loading.
- Deployment: Cloud Run with branch-based GitHub Actions CI/CD.
- Testing approach: DuckDB-backed mock client for unit tests and real BigQuery dev-dataset integration tests.

## Tech Stack

- Python 3.11
- FastAPI + Pydantic
- Google BigQuery + Google Cloud Storage
- MLflow model artifacts
- `uv` for dependency management
- `pytest` with unit and integration markers

## Architecture

```mermaid
graph TD
    A[Client] --> B[/app/v1 routers]
    B --> C[FastAPI Dependencies]
    C --> D[DI Container]
    D --> E[Services Layer]
    E --> F[GoogleCloudAPI]
    F --> G[(BigQuery)]
    F --> H[(Cloud Storage)]
    E --> I[ModelService]
```

### Key Design Choices

- `app/core/container.py`: central service wiring and lifecycle registration.
- `app/core/settings.py`: typed, immutable env configuration objects.
- `app/core/database_client.py`: BigQuery + GCS abstraction with parameterized query support.
- `app/core/errors/*`: unified error taxonomy mapped to consistent API error payloads.
- `config/bigquery_tables.yaml`: canonical table schema source for bootstrap scripts and test helpers.

## API Surface (v1)

Base prefix: `/app/v1`

### Health

- `GET /health/`

### Auth

- `POST /auth/google/code`

### Model (admin)

- `GET /model/metadata`
- `GET /model/manifest`
- `POST /model/reload`

### Transactions (user)

- `GET /transactions/labels`
- `GET /transactions/latest-entry`
- `POST /transactions/transform`
- `POST /transactions/upload`

### File Types (admin)

- `GET /filetypes/list`
- `POST /filetypes/register`
- `POST /filetypes/delete`

### Assets (user)

- `POST /assets/upload`
- `GET /assets/latest-entry`

### Reporting (admin)

- `GET /reporting/model-accuracy?starting_from=YYYY-MM-DD`

Interactive docs:

- Swagger: `/docs`
- ReDoc: `/redoc`

## Documentation Conventions

- Non-router Python modules use NumPy-style docstrings for maintainability and tool-friendly code understanding.
- Router endpoint handlers use Markdown-style sections to improve generated Swagger descriptions.
- Data model fields are documented directly in schema definitions for API clarity.

## Local Development

### 1. Prerequisites

- Python 3.11
- `uv`
- `gcloud` CLI authenticated for GCP access

### 2. Install Dependencies

```bash
./scripts/uv_sync.sh
```

### 3. Environment Variables

Required runtime variables:

```bash
export APP_JWT_SECRET="your-jwt-secret"
export APP_JWT_EXP_DELTA_MINUTES="60"
export GOOGLE_OAUTH_CLIENT_ID="your-google-client-id"
export GOOGLE_OAUTH_CLIENT_SECRET="your-google-client-secret"
export GCP_PROJECT_ID="your-gcp-project"
export GCP_LOCATION="europe-north1"
export GCP_BQ_DATASET="your_dataset_base"
export GCP_BUCKET_NAME="your-model-artifacts-bucket"
export ENV="dev"
```

Needed when running model-artifact tooling that reads MLflow metadata:

```bash
export MLFLOW_TRACKING_URI="https://your-mlflow-server"
```

### 4. Run API Locally

```bash
./scripts/run_local_terminal.sh
```

Direct command alternative:

```bash
uv run uvicorn app.main:app --host 0.0.0.0 --port 8081 --reload
```

### 5. Initialize BigQuery Tables (first-time setup)

```bash
uv run python scripts/init_gbq_tables.py dev
```

Supported environments: `dev`, `stg`, `prod`.

## Testing

### Unit Tests (DuckDB-backed mock BigQuery client)

```bash
uv run pytest -m "not integration"
```

### Integration Tests (real BigQuery dev dataset)

```bash
uv run pytest -m integration -s
```

Integration tests expect local development tokens in `.env` and refresh them automatically via script calls. You can also generate them manually:

```bash
uv run python scripts/create_local_dev_tokens.py
```

## Useful Scripts

- `scripts/uv_sync.sh`: sync dependencies from public + private package indexes.
- `scripts/run_local_terminal.sh`: load env, refresh local tokens, run FastAPI locally.
- `scripts/run_local_docker.sh`: build and run Docker image locally with ADC credentials.
- `scripts/init_gbq_tables.py`: bootstrap datasets/tables from `config/bigquery_tables.yaml`.
- `scripts/create_local_dev_tokens.py`: write local dev JWTs into `.env` for test/auth flows.

## CI/CD

Single workflow: `.github/workflows/deploy.yml`

- `main`: tests + deploy to Cloud Run (`prod`)
- `stg`: tests + deploy to Cloud Run (`stg`)
- `feature/*`: tests only

## Data Schema Contract

`config/bigquery_tables.yaml` is the canonical table contract used by:

1. `scripts/init_gbq_tables.py` for dataset/table initialization.
2. `tests/helpers/duckdb_mock_client.py` for schema-consistent mock behavior.

When table structure changes, update the YAML first, then update service logic and tests.
