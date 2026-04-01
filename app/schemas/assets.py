from pydantic import BaseModel, Field


class AssetUploadRequest(BaseModel):
    """Request model for uploading asset data fields to the database.

    This model captures the necessary information about the asset data being uploaded.
    """

    cash: float = Field(
        ...,
        description="The sum of all cash assets (ie. bank account balances)",
        examples=[2000.00],
        ge=0.00,
    )
    other_assets: float = Field(
        ...,
        description="The sum of all tangible assets (ie. car, valuables, if owned)",
        examples=[500.00],
        ge=0.00,
    )
    apartment: float = Field(
        ...,
        description="The value of the user's apartment (if owned)",
        examples=[150000.00],
        ge=0.00,
    )
    capital_assets_value: float = Field(
        ...,
        description="The market value of all capital assets (ie. stocks, mutual funds, if owned)",
        examples=[25000.00],
        ge=0.00,
    )
    capital_assets_unrealized_gains: float = Field(
        ...,
        description="The sum of all unrealized gains from capital assets (ie. stocks, mutual funds, if owned)",
        examples=[5000.00],
        ge=0.00,
    )
    mortgage: float = Field(
        ...,
        description="The value of the user's mortgage (if applicable)",
        examples=[-120000.00],
        le=0.00,
    )
    student_loan: float = Field(
        ...,
        description="The value of the user's student loan (if applicable)",
        examples=[-12000.00],
        le=0.00,
    )
    other_liabilities: float = Field(
        ...,
        description="The sum of all other liabilities (ie. credit card debt, if applicable)",
        examples=[-3000.00],
        le=0.00,
    )
    realized_capital_gains: float = Field(
        ...,
        description="The sum of all realized gains from capital assets for given period (ie. stocks, mutual funds, if applicable)",
        examples=[2000.00],
        ge=0.00,
    )
    realized_capital_losses: float = Field(
        ...,
        description="The sum of all realized losses from capital assets for given period (ie. stocks, mutual funds, if applicable)",
        examples=[-700.00],
        le=0.00,
    )
    date: str = Field(
        ...,
        description="The date of the balance sheet data, in the format 'YYYY-MM-DD'",
        examples=["2024-01-31"],
    )
