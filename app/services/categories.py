import logging
from typing import Dict, List

from app.core.errors.domain import DatabaseQueryError

logger = logging.getLogger(__name__)


class CategoriesService:
    """Service for managing category operations.

    This service provides an abstraction layer over database operations for categories,
    making it easier to test and mock.
    """

    def __init__(self, db_client):
        """Initialize the categories service.

        Args:
            db_client: Database client instance.
        """
        self.db_client = db_client

    def get_expenditure_categories(self) -> List[Dict[str, str]]:
        """Get all expenditure (transaction) categories.

        Returns:
            List of dictionaries containing expenditure category names, and comments
        """
        return self.__guery_cateogries_by_group("transaction")

    def get_asset_categories(self) -> List[Dict[str, str]]:
        """Get all asset categories.

        Returns:
            List of dictionaries containing asset category names, and comments
        """
        return self.__guery_cateogries_by_group("asset")

    def __guery_cateogries_by_group(self, group: str) -> List[Dict[str, str]]:
        """Private method to query categories by group.

        Args:
            group: The category group to filter by (e.g., 'transaction' or 'asset').

        Returns:
            List of dictionaries containing category names and comments for the specified group.
        """
        sql = f"""
        SELECT
            CategoryName AS name,
            CategoryComment AS comment
        FROM
            {self.db_client.dataset}.d_category
        WHERE
            CategoryGroup = '{group}'
            AND _RowStatus != 'd'
        GROUP BY
            1, 2 -- Group for case of duplication
        """  # nosec B608
        df = self.db_client.sql_to_pandas(sql)
        logger.debug(f"Fetched {group} categories from BigQuery:\n{df}")
        if df.empty:
            raise DatabaseQueryError(f"No categories found for group '{group}'")
        return df.to_dict(orient="records")
