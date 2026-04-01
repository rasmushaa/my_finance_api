"""Helpers for loading BigQuery table schemas from YAML."""

from __future__ import annotations

from functools import cache
from pathlib import Path
from typing import Any

import yaml

SCHEMA_CONFIG_PATH = (
    Path(__file__).resolve().parents[1] / "config" / "bigquery_tables.yaml"
)


@cache
def load_bigquery_table_definitions() -> dict[str, list[dict[str, Any]]]:
    payload = yaml.safe_load(SCHEMA_CONFIG_PATH.read_text(encoding="utf-8"))
    tables = payload.get("tables")
    if not isinstance(tables, dict):
        raise ValueError(
            f"Missing or invalid 'tables' in schema config: {SCHEMA_CONFIG_PATH}"
        )

    definitions: dict[str, list[dict[str, Any]]] = {}
    for table_name, table_payload in tables.items():
        if not isinstance(table_payload, dict):
            raise ValueError(
                f"Invalid table definition for '{table_name}' in {SCHEMA_CONFIG_PATH}"
            )
        columns = table_payload.get("columns")
        if not isinstance(columns, list):
            raise ValueError(
                f"Missing or invalid columns list for '{table_name}' in {SCHEMA_CONFIG_PATH}"
            )
        definitions[table_name] = columns

    return definitions
