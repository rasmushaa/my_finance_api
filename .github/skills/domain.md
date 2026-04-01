---
name: domain
description: >
  Domain knowledge for the my_finance_api project. Load this skill when adding
  features, writing tests, or making architectural decisions. Covers service
  patterns, dependency injection, schemas, documentation style, and testing conventions.
---

# MyFinance API — Domain Reference

## Read First

Always scan these files before making non-trivial changes:

| Purpose | File |
|---|---|
| BigQuery table schema source-of-truth | `config/bigquery_tables.yaml` |
| Table initialization from schema config | `scripts/init_gbq_tables.py` |
| Schema loader used by scripts/tests | `scripts/bigquery_table_config.py` |
| DI container and service wiring | `app/core/container.py` |
| Typed runtime settings | `app/core/settings.py` |
| Error base class and global handlers | `app/core/errors/base_error.py`, `app/core/errors/handlers.py` |
| API router registration | `app/main.py`, `app/api/v1.py` |

## Architecture Facts

- Services are resolved through `Container` in `app/core/container.py`.
- Pydantic request/response models belong in `app/schemas/`, not router/service files.
- Raise `AppError` subclasses for expected failures; rely on global error handlers.
- Canonical model features are in `app/schemas/model.py`. If changed, update model artifacts and tests.
- BigQuery schema names are case-sensitive and follow current table contracts (e.g. `UserEmail`, `UserRole`).

## Documentation Conventions

- Python docstrings: NumPy style.
- API endpoint docstrings: Markdown sections (`## Parameters`, `## Returns`, `## Raises`) for Swagger readability.
- Keep README and workflow comments aligned with real commands and branch behavior.

## Testing Conventions

- Prefer `DuckDBMockClient` (`tests/helpers/duckdb_mock_client.py`) over ad hoc DB mocks.
- Seeded test tables must match `config/bigquery_tables.yaml` columns exactly.
- Unit/API tests should keep auth/service overrides focused and minimal.
- Default local/CI test command: `pytest -m "not integration"`.

## Change Checklist

When touching schema, auth, or API contracts:

1. Update schema/config or Pydantic models first.
2. Update service logic and error handling.
3. Update unit tests and API tests.
4. Update README and workflow comments if behavior/commands changed.
