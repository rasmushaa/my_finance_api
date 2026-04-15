"""Asset snapshot service for user balance-sheet data."""

import logging

import pandas as pd

from app.core.errors.domain import DatabaseQueryError

logger = logging.getLogger(__name__)


class AssetService:
    """Persist and query user asset snapshots."""

    _CATEGORY_FIELDS = {
        "CASH": "cash",
        "OTHER-ASSETS": "other_assets",
        "APARTMENT": "apartment",
        "CAPITAL-ASSETS-PURCHASE-PRICE": "capital_assets_purchase_price",
        "UNREALIZED-CAPITAL-GAINS": "capital_assets_unrealized_gains",
        "MORTGAGE": "mortgage",
        "OTHER-LOANS": "other_liabilities",
        "STUDENT-LOAN": "student_loan",
        "REALIZED-CAPITAL-GAINS": "realized_capital_gains",
        "REALIZED-CAPITAL-LOSSES": "realized_capital_losses",
    }

    def __init__(self, db_client):
        """Initialize asset service.

        Parameters
        ----------
        db_client :
            Database client used for reads/writes to ``f_assets``.
        """
        self.db_client = db_client

    def upload_assets(
        self,
        cash: float,
        other_assets: float,
        apartment: float,
        capital_assets_market_value: float,
        capital_assets_unrealized_gains: float,
        mortgage: float,
        other_liabilities: float,
        student_loan: float,
        realized_capital_gains: float,
        realized_capital_losses: float,
        user_email: str,
        date: str,
    ):
        """Append one full balance-sheet snapshot to ``f_assets``.

        Snapshot fields are denormalized into category/value rows to keep storage
        consistent with transaction-style reporting patterns.

        Parameters
        ----------
        cash: float
            The sum of all cash assets (e.g. bank accounts)
        other_assets: float
            The sum of all other assets (e.g. cars, valuables)
        apartment: float
            The current market value of the user's apartment or house
        capital_assets_market_value: float
            The current market value of the user's capital assets (e.g. stocks, crypto)
        capital_assets_unrealized_gains: float
            The unrealized gains of the user's capital assets
        mortgage: float
            The current outstanding value of the user's mortgage
        other_liabilities: float
            The sum of all other liabilities (e.g. credit card debt, loans)
        student_loan: float
            The current outstanding value of the user's student loans
        realized_capital_gains: float
            The total realized capital gains for the current period
        realized_capital_losses: float
            The total realized capital losses for the current period
        user_email: str
            The email of the user, used to link the assets data to the user in the database
        date : str
            Snapshot date in ``YYYY-MM-DD`` format.
        """

        captital_assets_purchase_price = (  # The legacy tabel uses purchase price, which can be derived from market value and unrealized gains
            capital_assets_market_value - capital_assets_unrealized_gains
        )

        field_values = {
            "cash": cash,
            "other_assets": other_assets,
            "apartment": apartment,
            "capital_assets_purchase_price": captital_assets_purchase_price,
            "capital_assets_unrealized_gains": capital_assets_unrealized_gains,
            "mortgage": mortgage,
            "other_liabilities": other_liabilities,
            "student_loan": student_loan,
            "realized_capital_gains": realized_capital_gains,
            "realized_capital_losses": realized_capital_losses,
        }
        assets = {
            cat: field_values[field] for cat, field in self._CATEGORY_FIELDS.items()
        }
        df = pd.DataFrame(
            [
                {"UserEmail": user_email, "Date": date, "Category": k, "Value": v}
                for k, v in assets.items()
            ]
        )
        self.db_client.append_pandas_to_table(df, "f_assets")

    def get_latest_entry_stats(self, user_email: str) -> dict[str, float | str]:
        """Fetch latest full asset snapshot for a user.

        Parameters
        ----------
        user_email: str
            The email of the user to get the latest entry stats for.

        Returns
        -------
        dict[str, float | str]
            Mapping compatible with ``AssetEntryRequest`` fields.
        """
        sql = f"""
        WITH latest_date AS (
            SELECT
                MAX(Date) as latest_active_date
            FROM
                `{self.db_client.dataset}.f_assets`
            WHERE
                UserEmail = @user_email
                AND _RowStatus != @deleted_status
        )
        SELECT
            Date,
            Category,
            Value
        FROM
            `{self.db_client.dataset}.f_assets`
        WHERE
            UserEmail = @user_email
            AND _RowStatus != @deleted_status
            AND Date = (SELECT latest_active_date FROM latest_date)
        """  # nosec B608
        df = self.db_client.sql_to_pandas(
            sql,
            params={"user_email": user_email, "deleted_status": "d"},
        )
        if df.empty:
            raise DatabaseQueryError(
                message="No asset entries found for the user.",
                details={
                    "hint": "The user might not have uploaded any asset data yet, and thus there are no entries to retrieve.",
                    "user_email": user_email,
                },
            )
        date_str = df["Date"].iloc[0].isoformat()
        values = (
            df.set_index("Category")["Value"].rename(self._CATEGORY_FIELDS).to_dict()
        )
        values[
            "capital_assets_market_value"
        ] = (  # The frontend used the more fluent market value, compared to the legacy table
            values["capital_assets_purchase_price"]
            + values["capital_assets_unrealized_gains"]
        )
        return {"date": date_str, **values}
