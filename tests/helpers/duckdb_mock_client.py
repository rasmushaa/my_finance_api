"""Reusable DuckDB-backed mock database client for tests."""

from __future__ import annotations

import hashlib
import re
from datetime import date, datetime, time
from typing import Mapping
from unittest.mock import Mock

import duckdb
import pandas as pd

from scripts.bigquery_table_config import load_bigquery_table_definitions


class DuckDBMockClient:
    """A lightweight db_client replacement backed by in-memory DuckDB.

    Exposes the same methods used by services:
    - `sql_to_pandas(sql, params=None)`
    - `append_pandas_to_table(df, table_name)`
    - `execute_sql(sql, params=None)`

    Each callable is wrapped with `unittest.mock.Mock` so tests can assert calls.
    """

    def __init__(
        self,
        dataset: str = "test_dataset_dev",
        seed_tables: Mapping[str, pd.DataFrame] | None = None,
    ):
        self.dataset = dataset
        self._conn = duckdb.connect()
        self._conn.execute(f"CREATE SCHEMA {dataset}")

        if seed_tables:
            for table_name, df in seed_tables.items():
                self.seed_table(table_name, df)

        self.sql_to_pandas = Mock(side_effect=self._sql_to_pandas_impl)
        self.append_pandas_to_table = Mock(
            side_effect=self._append_pandas_to_table_impl
        )
        self.execute_sql = Mock(side_effect=self._execute_sql_impl)

    @staticmethod
    def _normalize_sql(sql: str) -> str:
        normalized = sql.replace("`", "").strip()
        normalized = normalized.replace(
            "CURRENT_TIMESTAMP()", "current_localtimestamp()"
        )
        return normalized.replace("CURRENT_TIMESTAMP", "current_localtimestamp()")

    @staticmethod
    def _sql_literal(value: object) -> str:
        if value is None:
            return "NULL"
        if isinstance(value, bool):
            return "TRUE" if value else "FALSE"
        if isinstance(value, (int, float)):
            return str(value)
        if isinstance(value, pd.Timestamp):
            text = value.isoformat()
        elif isinstance(value, (datetime, date, time)):
            text = value.isoformat()
        else:
            text = str(value)
        return "'" + text.replace("'", "''") + "'"

    @classmethod
    def _apply_params(cls, sql: str, params: Mapping[str, object] | None = None) -> str:
        if not params:
            return sql

        rendered = sql
        for key, value in params.items():
            pattern = re.compile(rf"@{re.escape(key)}\b")
            rendered = pattern.sub(cls._sql_literal(value), rendered)
        return rendered

    def _table_exists(self, table_name: str) -> bool:
        count = self._conn.execute(
            f"SELECT COUNT(*) FROM information_schema.tables "
            f"WHERE table_schema = '{self.dataset}' AND table_name = '{table_name}'"
        ).fetchone()[0]
        return bool(count)

    def _table_columns(self, table_name: str) -> list[str]:
        return [
            row[0]
            for row in self._conn.execute(
                "SELECT column_name FROM information_schema.columns "
                f"WHERE table_schema = '{self.dataset}' AND table_name = '{table_name}' "
                "ORDER BY ordinal_position"
            ).fetchall()
        ]

    def _validate_and_normalize_seed(
        self, table_name: str, df: pd.DataFrame
    ) -> pd.DataFrame:
        table_definitions = load_bigquery_table_definitions()
        if table_name not in table_definitions:
            raise ValueError(
                f"Seed table '{table_name}' is not declared in config/bigquery_tables.yaml"
            )

        expected_columns = [col["name"] for col in table_definitions[table_name]]
        expected_set = set(expected_columns)
        actual_set = set(df.columns)
        missing_columns = expected_set - actual_set
        extra_columns = actual_set - expected_set
        if missing_columns or extra_columns:
            raise ValueError(
                f"Seed table '{table_name}' schema mismatch. "
                f"Missing columns: {sorted(missing_columns)}. "
                f"Unexpected columns: {sorted(extra_columns)}. "
                f"Expected columns: {expected_columns}"
            )
        return df.loc[:, expected_columns].copy()

    def seed_table(self, table_name: str, df: pd.DataFrame) -> None:
        """Create or replace a table from a DataFrame seed."""
        normalized_df = self._validate_and_normalize_seed(table_name, df)
        self._conn.register("_seed_df", normalized_df)
        if self._table_exists(table_name):
            self._conn.execute(f"DROP TABLE {self.dataset}.{table_name}")
        self._conn.execute(
            f"CREATE TABLE {self.dataset}.{table_name} AS SELECT * FROM _seed_df"
        )

    def _sql_to_pandas_impl(
        self, sql: str, params: Mapping[str, object] | None = None
    ) -> pd.DataFrame:
        query = self._apply_params(self._normalize_sql(sql), params=params)
        return self._conn.execute(query).df()

    def _append_pandas_to_table_impl(self, df: pd.DataFrame, table_name: str) -> None:
        frame = df.copy()
        if "_RowStatus" not in frame.columns:
            frame["_RowStatus"] = "i"
        now = pd.Timestamp.now()
        if "_RowCreatedAt" not in frame.columns:
            frame["_RowCreatedAt"] = now
        if "_RowUpdatedAt" not in frame.columns:
            frame["_RowUpdatedAt"] = now
        if "_RowUploadHash" not in frame.columns:
            frame["_RowUploadHash"] = frame.apply(
                lambda row: int.from_bytes(
                    hashlib.sha256(str(tuple(row)).encode()).digest()[:8], "big"
                ),
                axis=1,
            )
            frame["_RowUploadHash"] = frame["_RowUploadHash"] & 0x7FFFFFFFFFFFFFFF

        self._conn.register("_insert_df", frame)

        if self._table_exists(table_name):
            destination_columns = self._table_columns(table_name)
            source_columns = [
                col for col in frame.columns if col in destination_columns
            ]
            if not source_columns:
                raise ValueError(
                    f"No matching columns for insert into {self.dataset}.{table_name}"
                )
            columns_sql = ", ".join(source_columns)
            self._conn.execute(
                f"INSERT INTO {self.dataset}.{table_name} ({columns_sql}) "
                f"SELECT {columns_sql} FROM _insert_df"
            )
        else:
            self._conn.execute(
                f"CREATE TABLE {self.dataset}.{table_name} AS SELECT * FROM _insert_df"
            )

    def _execute_sql_impl(
        self, sql: str, params: Mapping[str, object] | None = None
    ) -> int:
        """Execute SQL and return affected rows for basic UPDATE/DELETE statements."""
        query = self._apply_params(self._normalize_sql(sql), params=params)

        update_match = re.match(
            r"(?is)^UPDATE\s+([^\s]+)\s+SET\s+.+?\s+WHERE\s+(.+?);?$",
            query,
        )
        if update_match:
            table_name = update_match.group(1)
            where_clause = update_match.group(2).rstrip(";")
            affected_rows = self._conn.execute(
                f"SELECT COUNT(*) FROM {table_name} WHERE {where_clause}"
            ).fetchone()[0]
            self._conn.execute(query)
            return int(affected_rows)

        delete_match = re.match(
            r"(?is)^DELETE\s+FROM\s+([^\s]+)\s+WHERE\s+(.+?);?$",
            query,
        )
        if delete_match:
            table_name = delete_match.group(1)
            where_clause = delete_match.group(2).rstrip(";")
            affected_rows = self._conn.execute(
                f"SELECT COUNT(*) FROM {table_name} WHERE {where_clause}"
            ).fetchone()[0]
            self._conn.execute(query)
            return int(affected_rows)

        self._conn.execute(query)
        return 0
