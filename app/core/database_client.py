import logging
import os

import pandas as pd
import pandas_gbq

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

    def __init__(self):
        self.__project_id = os.getenv("GCP_PROJECT_ID")
        self.__dataset = os.getenv("GCP_BQ_DATASET") + "_" + os.getenv("ENV", "dev")
        self.__location = os.getenv("GCP_LOCATION")

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

    def sql_to_pandas(self, sql: str) -> pd.DataFrame:
        """Run a regular SQL query and return a pandas DataFrame.

        Inputs
        ------
        sql : string
            A regular SQL query

        Returns
        -------
        df : DataFrame
        """
        logger.debug(f"Running SQL query:\n{sql}")
        df = pandas_gbq.read_gbq(
            sql,
            project_id=self.__project_id,
            location=self.__location,
            progress_bar_type=None,
        )  # Use the system default credentials/Cloud Run SA
        logger.debug(f"Query result:\n{df}")
        return df

    def write_pandas_to_table(self, df: pd.DataFrame, table_name: str):
        """Push a DataFrame to BigQuery.

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
        """
        table_schema = []  # [{'name': 'col1', 'type': 'STRING'},...]
        for col in df.columns:
            if "date" in col.lower():
                table_schema.append({"name": col, "type": "DATE"})
            elif "object" in str(df[col].dtype):
                table_schema.append({"name": col, "type": "STRING"})
            elif "float" in str(df[col].dtype):
                table_schema.append({"name": col, "type": "FLOAT64"})
            elif "datetime" in str(df[col].dtype):
                table_schema.append({"name": col, "type": "TIMESTAMP"})

        pandas_gbq.to_gbq(
            df,
            destination_table=f"{self.__dataset}.{table_name}",
            project_id=self.__project_id,
            location=self.__location,
            table_schema=table_schema,
            if_exists="append",
        )  # Use default the system default credentials/Cloud Run SA
        logger.debug(
            f"Pushed DataFrame to BigQuery table {self.__dataset}.{table_name} with schema:\n{table_schema}"
        )
