import hashlib
import logging

import pandas as pd
import pandas_gbq
from google.api_core.exceptions import GoogleAPICallError
from google.cloud import bigquery
from google.cloud.exceptions import Forbidden, NotFound

from app.core.errors.infra import DatabaseInternalError
from app.core.settings import BigQueryConfig

logger = logging.getLogger(__name__)


class GoogleCloudAPI:
    """A singleton wrapper class for Google Cloud APIs, including BigQuery and Cloud
    Storage.

    The class contains all information about the project,
    such as project id, dataset, location, bucket name and directory,
    which are loaded from environment variables.

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

    def execute_sql(self, sql: str) -> int:
        """Run a regular SQL query without returning results, used for DDL and DML
        operations.

        Inputs
        ------
        sql : string
            A regular SQL query

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
            job = client.query(sql)
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

    def sql_to_pandas(self, sql: str) -> pd.DataFrame:
        """Run a regular SQL query and return a pandas DataFrame.

        Inputs
        ------
        sql : string
            A regular SQL query

        Returns
        -------
        df : DataFrame

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
            df = pandas_gbq.read_gbq(
                sql,
                project_id=self.__project_id,
                location=self.__location,
                progress_bar_type=None,
            )  # Use the system default credentials/Cloud Run SA
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

        Inputs
        ------
        df : pd.DataFrame
            A regular DataFrame
        table_name : str
            The name of destination table in BigQuery, without dataset prefix
        """

        self.__write_pandas_to_table(df, table_name, if_exists="append")

    def __write_pandas_to_table(
        self, df: pd.DataFrame, table_name: str, if_exists: str
    ):
        """Push a DataFrame to BigQuery.

        Basic metadata columns are added to the DataFrame for traceability and auditing purposes,

        A new table will be create, if the destination does not exists,
        however, pyarrows has a bug and it fails for datetime columns,
        thus the schema must be constructed manually from pandas to GBQ format.
        The mode is locked to Append only, to prevent accidental overwrites

        Inputs
        ------
        df : pd.DataFrame
            A regular DataFrame
        table_name : str
            The name of destination table in BigQuery, without dataset prefix
        if_exists : str
            Behavior when the destination table already exists. Default is "append".
            Allowed values are "fail", "replace", "append".
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
        """Add metadata columns for table operations.

        Details
        -------
        - _RowStatus: 'i' for inserted, 'u' for updated, 'd' for deleted. This allows for soft deletes and tracking changes over time.
        - _RowCreatedAt: Timestamp of when the row was created.
        - _RowUpdatedAt: Timestamp of when the row was last updated.
        - _RowUploadHash: A hash of the original row data (including metadata columns), used for change detection and auditing.

        Parameters
        ----------
        df : pd.DataFrame
            A regular DataFrame

        Returns
        -------
        df : pd.DataFrame
            The input DataFrame with added metadata columns
        """
        df = df.copy()
        df["_RowStatus"] = "i"
        now = pd.Timestamp.now(tz="UTC")
        df["_RowCreatedAt"] = now
        df["_RowUpdatedAt"] = now
        df["_RowUploadHash"] = df.apply(
            lambda row: int.from_bytes(
                hashlib.sha256(str(tuple(row)).encode()).digest()[:8], "big"
            ),
            axis=1,
        )
        return df
