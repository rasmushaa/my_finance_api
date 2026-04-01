import logging

import pandas as pd

logger = logging.getLogger(__name__)


class AssetService:

    def __init__(self, db_client):
        """Initialize the IO service to handle file operations.

        Parameters
        ----------
            db_client: Database client instance.
        """
        self.db_client = db_client

    def upload_assets(
        self,
        cash: float,
        other_assets: float,
        apartment: float,
        capital_assets_value: float,
        capital_assets_unrealized_gains: float,
        mortgage: float,
        other_liabilities: float,
        student_loan: float,
        realized_capital_gains: float,
        realized_capital_losses: float,
        user_email: str,
        date: str,
    ):
        """Append the user input balance sheet data to the assets table in the database.

        All new rows are marked with _RowStatus 'i' for inserted, and the current
        timestamp is added to _RowCreatedAt and _RowUpdatedAt.

        Parameters
        ----------
        cash: float
            The sum of all cash assets (e.g. bank accounts)
        other_assets: float
            The sum of all other assets (e.g. cars, valuables)
        apartment: float
            The current market value of the user's apartment or house
        capital_assets_value: float
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
        date: str
            The date of the balance sheet data, in the format 'YYYY-MM-DD'
        """
        assets = {
            "CASH": cash,
            "OTHER-ASSETS": other_assets,
            "APARTMENT": apartment,
            "CAPITAL-ASSETS-VALUE": capital_assets_value,
            "UNREALIZED-CAPITAL-GAINS": capital_assets_unrealized_gains,
            "MORTGAGE": mortgage,
            "OTHER-LOANS": other_liabilities,
            "STUDENT-LOAN": student_loan,
            "REALIZED-CAPITAL-GAINS": realized_capital_gains,
            "REALIZED-CAPITAL-LOSSES": realized_capital_losses,
        }
        df = pd.DataFrame(
            [
                {"UserEmail": user_email, "Date": date, "Category": k, "Value": v}
                for k, v in assets.items()
            ]
        )
        self.db_client.append_pandas_to_table(df, "f_assets")
