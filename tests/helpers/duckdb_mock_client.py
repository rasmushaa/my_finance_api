"""Reusable DuckDB-backed mock database client for tests."""

from __future__ import annotations

import re
from typing import Mapping
from unittest.mock import Mock

import duckdb
import pandas as pd


class DuckDBMockClient:
    """A lightweight db_client replacement backed by in-memory DuckDB.

    Exposes the same methods used by services:
    - `sql_to_pandas(sql)`
    - `append_pandas_to_table(df, table_name)`
    - `execute_sql(sql)`

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
        return sql.replace("`", "").strip()

    def _table_exists(self, table_name: str) -> bool:
        count = self._conn.execute(
            f"SELECT COUNT(*) FROM information_schema.tables "
            f"WHERE table_schema = '{self.dataset}' AND table_name = '{table_name}'"
        ).fetchone()[0]
        return bool(count)

    def seed_table(self, table_name: str, df: pd.DataFrame) -> None:
        """Create or replace a table from a DataFrame seed."""
        self._conn.register("_seed_df", df.copy())
        if self._table_exists(table_name):
            self._conn.execute(f"DROP TABLE {self.dataset}.{table_name}")
        self._conn.execute(
            f"CREATE TABLE {self.dataset}.{table_name} AS SELECT * FROM _seed_df"
        )

    def _sql_to_pandas_impl(self, sql: str) -> pd.DataFrame:
        return self._conn.execute(self._normalize_sql(sql)).df()

    def _append_pandas_to_table_impl(self, df: pd.DataFrame, table_name: str) -> None:
        frame = df.copy()
        if "_RowStatus" not in frame.columns:
            frame["_RowStatus"] = "i"

        self._conn.register("_insert_df", frame)

        if self._table_exists(table_name):
            self._conn.execute(
                f"INSERT INTO {self.dataset}.{table_name} SELECT * FROM _insert_df"
            )
        else:
            self._conn.execute(
                f"CREATE TABLE {self.dataset}.{table_name} AS SELECT * FROM _insert_df"
            )

    def _execute_sql_impl(self, sql: str) -> int:
        """Execute SQL and return affected rows for basic UPDATE/DELETE statements."""
        query = self._normalize_sql(sql)

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
