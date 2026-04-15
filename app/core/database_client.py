"""Google Cloud data-access client.

This module wraps BigQuery and GCS operations used by service-layer components. It
provides:
- SQL execution for DML/DDL
- SQL-to-DataFrame reads
- DataFrame append writes
- model artifact and manifest reads from Cloud Storage
"""

import hashlib
import logging
from datetime import date, datetime, time
from typing import Any, Mapping

import pandas as pd
import pandas_gbq
from google.api_core.exceptions import GoogleAPICallError
from google.cloud import bigquery, storage
from google.cloud.exceptions import Forbidden, NotFound

from app.core.errors.infra import DatabaseInternalError
from app.core.settings import BigQueryConfig

logger = logging.getLogger(__name__)


class GoogleCloudAPI:
    """A singleton wrapper class for Google Cloud APIs, including BigQuery and Cloud
    Storage.

    The client keeps runtime-scoped project settings (project, dataset, location,
    bucket), loaded from ``BigQueryConfig``.

    Details
    -------
    The ENV variable suffix encodes the environment (dev, staging, prod)
    and is used to separate datasets for different environments.
    """

    def __init__(self, config: BigQueryConfig | None = None):
        gcp_config = config or BigQueryConfig.from_env()
        self.__project_id = gcp_config.project_id
        self.__dataset = gcp_config.dataset
        self.__location = gcp_config.location
        self.__bucket_name = gcp_config.bucket_name

    @property
    def dataset(self) -> str:
        """Get the dataset name with environment suffix, e.g. 'my_dataset_dev'.

        Mainly intended to use in external files to format SQL queries,
        to ensure the correct dataset is used for different environments.

        Returns
        -------
        dataset : str
             The dataset name with environment suffix
        """
        return self.__dataset

    @staticmethod
    def __infer_bq_param_type(value: Any) -> str:
        """Infer BigQuery scalar parameter type from a Python value."""
        if isinstance(value, bool):
            return "BOOL"
        if isinstance(value, int):
            return "INT64"
        if isinstance(value, float):
            return "FLOAT64"
        if isinstance(value, datetime):
            return "TIMESTAMP"
        if isinstance(value, date):
            return "DATE"
        if isinstance(value, time):
            return "TIME"
        return "STRING"

    def __build_query_job_config(
        self, params: Mapping[str, Any] | None
    ) -> bigquery.QueryJobConfig | None:
        """Build BigQuery QueryJobConfig for named scalar parameters.

        Parameters
        ----------
        params : Mapping[str, Any] | None
            Named parameter mapping for ``@param`` placeholders in SQL.

        Returns
        -------
        bigquery.QueryJobConfig | None
            Query config with typed scalar parameters, or ``None`` when empty.
        """
        if not params:
            return None

        query_params: list[bigquery.ScalarQueryParameter] = []
        for key, value in params.items():
            param_type = self.__infer_bq_param_type(value)
            query_params.append(bigquery.ScalarQueryParameter(key, param_type, value))

        return bigquery.QueryJobConfig(query_parameters=query_params)

    def execute_sql(self, sql: str, params: Mapping[str, Any] | None = None) -> int:
        """Run a regular SQL query without returning results, used for DDL and DML
        operations.

        Parameters
        ----------
        sql : str
            SQL query string.
        params : Mapping[str, Any] | None
            Optional named query parameters used with `@param` placeholders.

        Returns
        -------
        affected_rows : int
            The number of rows affected by the query, if applicable (e.g. for DML statements). For DDL statements, this will typically be 0.

        Raises
        ------
        Forbidden
            When access is denied to BigQuery resources
        NotFound
            When the specified table or dataset does not exist
        GoogleAPICallError
            For other BigQuery API errors
        """
        logger.debug(f"Executing SQL query:\n{sql}")
        try:
            client = bigquery.Client(
                project=self.__project_id, location=self.__location
            )
            job_config = self.__build_query_job_config(params)
            job = client.query(sql, job_config=job_config)
            job.result()  # Wait for completion

            logger.debug(
                f"SQL query executed successfully. Total bytes processed: {job.total_bytes_processed}, Rows affected: {job.num_dml_affected_rows}"
            )
            return job.num_dml_affected_rows

        except Forbidden as e:
            logger.error(f"BigQuery access denied: {str(e)}")
            raise DatabaseInternalError(details={"error": str(e)})

        except NotFound as e:
            logger.error(f"BigQuery resource not found: {str(e)}")
            raise DatabaseInternalError(details={"error": str(e)})

        except GoogleAPICallError as e:
            logger.error(f"BigQuery API error: {str(e)}")
            raise DatabaseInternalError(details={"error": str(e)})

    def sql_to_pandas(
        self, sql: str, params: Mapping[str, Any] | None = None
    ) -> pd.DataFrame:
        """Run SQL and return the result as a pandas DataFrame.

        Parameters
        ----------
        sql : str
            SQL query string.
        params : Mapping[str, Any] | None
            Optional named query parameters used with `@param` placeholders.

        Returns
        -------
        pd.DataFrame
            Query results.

        Raises
        ------
        Forbidden
            When access is denied to BigQuery resources
        NotFound
            When the specified table or dataset does not exist
        GoogleAPICallError
            For other BigQuery API errors
        """
        logger.debug(f"Running SQL query:\n{sql}")
        try:
            client = bigquery.Client(
                project=self.__project_id, location=self.__location
            )
            job_config = self.__build_query_job_config(params)
            query_job = client.query(sql, job_config=job_config)
            df = query_job.to_dataframe(create_bqstorage_client=False)
            logger.debug(f"Query result:\n{df}")
            return df

        except Forbidden as e:
            logger.error(f"BigQuery access denied: {str(e)}")
            raise DatabaseInternalError(details={"error": str(e)})

        except NotFound as e:
            logger.error(f"BigQuery resource not found: {str(e)}")
            raise DatabaseInternalError(details={"error": str(e)})

        except GoogleAPICallError as e:
            logger.error(f"BigQuery API error: {str(e)}")
            raise DatabaseInternalError(details={"error": str(e)})

    def append_pandas_to_table(self, df: pd.DataFrame, table_name: str):
        """Append a DataFrame to an existing BigQuery table.

        The table must already exist, and the schema must match the DataFrame.
        This method is used for appending new rows to existing tables.

        Parameters
        ----------
        df : pd.DataFrame
            DataFrame to append.
        table_name : str
            Destination table name without dataset prefix.
        """

        self.__write_pandas_to_table(df, table_name, if_exists="append")

    def download_to_filename(self, blob_path: str, destination_file: str):
        """Download a single object from GCS to a local file path.

        Parameters
        ----------
        blob_path : str
            Object path in GCS (for example ``"model/manifest.json"``).
        destination_file : str
            Local destination file path.
        """
        # TODO: Consider refactoring to a separate GCS client class if it grows too large or complex,
        try:
            client = storage.Client(project=self.__project_id)
            blob = client.bucket(self.__bucket_name).blob(blob_path)
            blob.download_to_filename(destination_file)
            logger.debug(f"Downloaded '{blob_path}' from GCS to '{destination_file}'")

        except Exception as e:
            logger.error(f"Error downloading file from GCS: {str(e)}")
            raise DatabaseInternalError(
                message="Error downloading file from GCS", details={"error": str(e)}
            )

    def list_blobs(self, prefix: str) -> list[str]:
        """List object paths in GCS under a prefix.

        Parameters
        ----------
        prefix : str
            GCS prefix to list (for example ``"model/prod/1/"``).

        Returns
        -------
        list[str]
            Object paths matching the prefix.
        """
        try:
            client = storage.Client(project=self.__project_id)
            blobs = client.bucket(self.__bucket_name).list_blobs(prefix=prefix)
            return [blob.name for blob in blobs]
        except Exception as e:
            logger.error(f"Error listing blobs from GCS: {str(e)}")
            raise DatabaseInternalError(
                message="Error listing blobs from GCS", details={"error": str(e)}
            )

    def __write_pandas_to_table(
        self, df: pd.DataFrame, table_name: str, if_exists: str
    ):
        """Write a DataFrame to BigQuery via ``pandas_gbq``.

        Metadata columns are appended before upload for auditability.
        Schema is inferred from DataFrame dtypes and passed explicitly to avoid pyarrow
        edge cases with date/datetime columns.

        Parameters
        ----------
        df : pd.DataFrame
            DataFrame to write.
        table_name : str
            Destination table name without dataset prefix.
        if_exists : str
            Behavior when destination table exists (``"fail"``, ``"replace"``,
            ``"append"``).
        """
        table_schema = []  # [{'name': 'col1', 'type': 'STRING'},...]
        for i, col in enumerate(df.columns):
            series = df.iloc[:, i]
            if "date" in col.lower():
                table_schema.append({"name": col, "type": "DATE"})
            elif "object" in str(series.dtype):
                table_schema.append({"name": col, "type": "STRING"})
            elif "float" in str(series.dtype):
                table_schema.append({"name": col, "type": "FLOAT64"})
            elif "datetime" in str(series.dtype):
                table_schema.append({"name": col, "type": "TIMESTAMP"})

        df = self.__add_row_metadata(df)

        pandas_gbq.to_gbq(
            df,
            destination_table=f"{self.__dataset}.{table_name}",
            project_id=self.__project_id,
            location=self.__location,
            table_schema=table_schema,
            if_exists=if_exists,
        )  # Use default the system default credentials/Cloud Run SA
        logger.debug(
            f"Pushed {df.shape[0]} rows to '{self.__dataset}.{table_name}' [if_exists={if_exists}] with schema:\n{table_schema}"
        )

    def __add_row_metadata(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add row-level metadata columns used in warehouse tables.

        Details
        -------
        - ``_RowStatus``: ``"i"`` for inserted rows.
        - ``_RowCreatedAt``: UTC creation timestamp.
        - ``_RowUpdatedAt``: UTC last-update timestamp.
        - ``_RowUploadHash``: stable 64-bit hash for traceability.

        Parameters
        ----------
        df : pd.DataFrame
            Input DataFrame.

        Returns
        -------
        df : pd.DataFrame
            Copy of input DataFrame with metadata columns added.
        """
        df = df.copy()
        df["_RowStatus"] = "i"
        now = pd.Timestamp.now(tz="UTC")
        df["_RowCreatedAt"] = now
        df["_RowUpdatedAt"] = now
        df["_RowUploadHash"] = df.apply(
            lambda row: int.from_bytes(
                hashlib.sha256(str(tuple(row)).encode()).digest()[:8], "big"
            )
            & 0x7FFFFFFFFFFFFFFF,
            axis=1,
        )
        return df
