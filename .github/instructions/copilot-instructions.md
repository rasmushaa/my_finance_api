# Copilot Instructions for `my_finance_api`

## Project Context

This repository is a FastAPI backend for personal finance ingestion and ML-based transaction categorization.

Primary goals:

- Keep architecture clean but practical.
- Keep tests reliable and explicit.
- Keep BigQuery schema contracts aligned across scripts, services, and tests.

## Architecture Rules

- Resolve services through the DI container (`app/core/container.py`).
- Keep API contracts in `app/schemas/`.
- Keep business logic in `app/services/`.
- Use `AppError` subclasses for expected failures (`app/core/errors/`).
- Do not move script-only concerns into app runtime unless required.

## BigQuery Schema Rules

- Source of truth: `config/bigquery_tables.yaml`.
- Table init script: `scripts/init_gbq_tables.py`.
- Loader: `scripts/bigquery_table_config.py`.
- Test mock DB seeds are validated against this same YAML via `tests/helpers/duckdb_mock_client.py`.
- Preserve exact table/column casing (for example `UserEmail`, `UserRole`).

## Documentation Style

- Python docstrings: NumPy style.
- Router endpoint docstrings: Markdown sections for Swagger (`## Parameters`, `## Returns`, `## Raises`).
- Keep README and workflow comments synchronized with actual commands and branch behavior.

## Testing Guidance

- Default test run: `pytest -m "not integration"`.
- Prefer shared test helpers (`DuckDBMockClient`, fake services) over one-off mocks.
- When changing schema/contracts, update tests in the same change.

## Common Files to Check Before Editing

- `README.md`
- `.github/workflows/deploy.yml`
- `config/bigquery_tables.yaml`
- `app/core/container.py`
- `app/core/settings.py`
- `app/api/dependencies.py`
- `tests/helpers/duckdb_mock_client.py`
