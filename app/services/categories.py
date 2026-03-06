import logging
from typing import List

logger = logging.getLogger(__name__)


class CategoriesService:
    """Service for managing category operations.

    This service provides an abstraction layer over database operations for categories,
    making it easier to test and mock.
    """

    def __init__(self, db_client=None):
        """Initialize the categories service.

        Args:
            db_client: Database client instance. If None, uses the default gcp singleton.
        """
        self.db_client = db_client

    def get_expenditure_categories(self) -> List[str]:
        """Get all expenditure (transaction) categories.

        Returns:
            List of expenditure category names.
        """
        sql = f"""
        SELECT
            Name
        FROM
            {self.db_client.dataset}.d_category
        WHERE
            Type = 'transaction'
        GROUP BY
            1 -- Group for case of duplication
        """  # nosec B608
        df = self.db_client.sql_to_pandas(sql)
        logger.debug(f"Fetched expenditure categories from BigQuery:\n{df}")
        return df["Name"].to_list()

    def get_asset_categories(self) -> List[str]:
        """Get all asset categories.

        Returns:
            List of asset category names.
        """
        sql = f"""
        SELECT
            Name
        FROM
            {self.db_client.dataset}.d_category
        WHERE
            Type = 'asset'
        GROUP BY
            1 -- Group for case of duplication
        """  # nosec B608
        df = self.db_client.sql_to_pandas(sql)
        logger.debug(f"Fetched asset categories from BigQuery:\n{df}")
        return df["Name"].to_list()
