---
name: domain
description: >
  Domain knowledge for the my_finance_api project. Load this skill when adding
  features, writing tests, or making architectural decisions. Covers service
  patterns, dependency injection, schemas, and coding conventions for this repo.
---

# MyFinance API — Domain Reference

## Key Files to Read Before Making Changes

Always read these files **before** adding, modifying, or reviewing code:

| Purpose | File |
|---------|------|
| The actula bigquery schemas | `scripts/init_gbq_tables.py` |
| DI container & service wiring | `app/core/container.py` |
| Auth schemas & JWT logic | `app/schemas/auth.py`, `app/services/jwt.py` |
| Exception hierarchy | `app/core/exceptions/base.py` |
| Router registration | `app/main.py`, `app/api/routers/__init__.py` |

## Architecture Facts

- **Dependency injection**: all services are resolved through `Container`. Never instantiate services directly; register them as singletons via `container.register(...)`.
- **Schemas live in `app/schemas/`**: one file per domain area (`model.py`, `auth.py`, `io.py`, …). Add new Pydantic models there, not inside routers or services.
- **Exceptions**: raise only subclasses of `AppError` (from `app/core/exceptions/base.py`). The global `app_error_handler` converts them to HTTP responses automatically.
- **ML canonical features**: `date`, `receiver`, `amount` (defined in `app/schemas/model.py`). Any change to these must be reflected in `model_artifacts/` and tests.

## Behavioral Guidelines

- Follow existing patterns exactly — match function signatures, docstring style, and import order found in neighbouring files.
- When writing tests, mirror the structure of existing test files (e.g. `tests/test_api_auth.py`): use `pytest`, mock via DI container overrides
