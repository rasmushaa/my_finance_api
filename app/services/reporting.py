"""Reporting service queries for analytics-oriented API endpoints."""

import pandas as pd


class ReportingService:
    """Build aggregated reporting tables from warehouse facts."""

    def __init__(self, db_client):
        """Initialize reporting service.

        Parameters
        ----------
        db_client :
            Database client used for analytical SQL queries.
        """
        self.db_client = db_client

    def get_model_accuracy_table(self, starting_from: str) -> pd.DataFrame:
        """Get a table of model accuracy metrics for all models, starting from a given
        date.

        Parameters
        ----------
        starting_from : str
            Lower date bound in ``YYYY-MM-DD`` format.

        Returns
        -------
        pd.DataFrame
            Monthly micro/macro accuracy rows per model metadata group.
        """

        sql = f"""
        WITH joining AS (
            SELECT
                FORMAT_DATETIME("%Y-%m", Date) as year_month,
                Category as category,
                CAST(Category = PredictedCategory AS INTEGER) as is_correct,
                ModelName as model_name,
                ModelAlias as model_alias,
                ModelVersion as model_version,
                ModelCommitSHA as model_commit_sha,
                ModelCommitHeadSHA as model_commit_head_sha,
                ModelArchitecture as model_architecture
            FROM
                `{self.db_client.dataset}.f_transactions` as l
            LEFT JOIN
                `{self.db_client.dataset}.f_predictions` as r
            ON
                l.RowProcessingID = r.RowProcessingID
            WHERE
                l._RowStatus != @deleted_status
                AND r._RowStatus != @deleted_status
                AND Date > DATE(@starting_from)
        ),
        micro_accuracy AS (
        SELECT
            year_month,
            'ALL' AS category,
            AVG(is_correct) AS accuracy,
            model_name,
            model_alias,
            model_version,
            model_commit_sha,
            model_commit_head_sha,
            model_architecture
        FROM
            joining
        GROUP BY
            1,2,4,5,6,7,8,9
        ),
        macro_accuracy AS (
        SELECT
            year_month,
            category,
            AVG(is_correct) AS accuracy,
            model_name,
            model_alias,
            model_version,
            model_commit_sha,
            model_commit_head_sha,
            model_architecture
        FROM
            joining
        GROUP BY
            1,2,4,5,6,7,8,9
        )
        SELECT
        *
        FROM
            micro_accuracy
        UNION ALL
        SELECT
        *
        FROM
            macro_accuracy
        ORDER BY
            1,2,4
        """  # nosec B608
        df = self.db_client.sql_to_pandas(
            sql,
            params={"starting_from": starting_from, "deleted_status": "d"},
        )
        return df
