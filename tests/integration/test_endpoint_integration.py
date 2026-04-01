"""Basic integration test for transaction processing flow.

The test uses the actual BigQuery Dev environment and the local FastAPI app instance.
The FastAPI has the privilidges of the terminal user running the test. Remember to re
create local dev tokens if expired and update .env file accordingly.

Run `uv run pytest -m integration -s` to execute the test and see print statements for
debugging.
"""

import io
import logging
import os
import subprocess

import dotenv
import pandas as pd
import pytest
from fastapi.testclient import TestClient

from app.main import app

logger = logging.getLogger(__name__)

API_BASE_URL = ""
MOCK_FILE_NAME = "local-integrtion-mock-data"


@pytest.fixture(scope="module")
def integration_env():
    """Prepare integration credentials lazily when integration tests actually run."""
    subprocess.run(
        ["uv", "run", "python", "scripts/create_local_dev_tokens.py"],
        check=True,
    )  # Refresh local dev tokens
    dotenv.load_dotenv(override=True)

    required = ["LOCAL_DEV_ADMIN_TOKEN", "LOCAL_DEV_USER_TOKEN"]
    missing = [key for key in required if not os.getenv(key)]
    if missing:
        pytest.fail(
            f"Missing required integration environment variables: {', '.join(missing)}"
        )


@pytest.mark.integration
def test_asset_integration(integration_env):

    with TestClient(app) as client:

        # Upload asset data
        response = client.post(
            API_BASE_URL + "app/v1/assets/upload",
            json={
                "cash": 1000.0,
                "other_assets": 500.0,
                "apartment": 50000.0,
                "capital_assets_value": 25000.0,
                "capital_assets_unrealized_gains": 5000.0,
                "mortgage": -120000.0,
                "student_loan": -12000.0,
                "other_liabilities": -3000.0,
                "realized_capital_gains": 2000.0,
                "realized_capital_losses": -700.0,
                "date": "2024-01-31",
            },
            headers={"Authorization": f"Bearer {os.environ['LOCAL_DEV_ADMIN_TOKEN']}"},
        )
        logger.info(f"Upload asset response: {response.status_code} {response.text}")
        assert response.status_code == 200, "Failed to upload asset data"


@pytest.mark.integration
def test_transaction_integration(integration_env):

    df_mock = pd.DataFrame(
        {
            "date": ["2023-01-01", "2023-01-02"],
            "amount": [100.0, 200.0],
            "receiver": ["Alice", "Bob"],
            "category": ["Food", "Transport"],
            "description": ["Grocery shopping", "Taxi ride"],
        }
    )

    with TestClient(app) as client:

        # 1. (Soft) Delete existing file type and related entries to ensure clean state
        response = client.post(
            API_BASE_URL + "app/v1/transactions/delete-filetype",
            json={"file_name": MOCK_FILE_NAME},
            headers={"Authorization": f"Bearer {os.environ['LOCAL_DEV_ADMIN_TOKEN']}"},
        )
        logger.info(
            f"Delete file type response: {response.status_code} {response.text}"
        )

        # 2. Create new file type
        response = client.post(
            API_BASE_URL + "app/v1/transactions/register-filetype",
            json={
                "cols": df_mock.columns.tolist(),
                "file_name": MOCK_FILE_NAME,
                "date_col": "date",
                "date_col_format": "%Y-%m-%d",
                "amount_col": "amount",
                "receiver_col": "receiver",
            },
            headers={"Authorization": f"Bearer {os.environ['LOCAL_DEV_ADMIN_TOKEN']}"},
        )
        logger.info(
            f"Create file type response: {response.status_code} {response.text}"
        )
        assert response.status_code == 200, "Failed to create file type"

        # 3. Transform and add predictions to the mock data using the API
        response = client.post(
            API_BASE_URL + "app/v1/transactions/transform",
            files={"file": ("mock_data.csv", df_mock.to_csv(index=False), "text/csv")},
            headers={"Authorization": f"Bearer {os.environ['LOCAL_DEV_USER_TOKEN']}"},
        )
        logger.info(f"Transform CSV response: {response.status_code} {response.text}")
        assert response.status_code == 200, "Failed to transform CSV"

        # 4. Open the transformed CSV response and verify the content
        transformed_df = pd.read_csv(io.StringIO(response.text))
        logger.info(f"Transformed DataFrame:\n{transformed_df}")
        assert transformed_df.columns.tolist() == [
            "Date",
            "Amount",
            "Receiver",
            "Category",
            "_RowProcessingID",
        ], "Transformed columns do not match expected"
        assert len(transformed_df) == len(
            df_mock
        ), "Transformed row count does not match input"

        # 5. Append the transformed data to the transactions table
        response = client.post(
            API_BASE_URL + "app/v1/transactions/upload",
            files={
                "file": (
                    "transformed_data.csv",
                    transformed_df.to_csv(index=False),
                    "text/csv",
                )
            },
            headers={"Authorization": f"Bearer {os.environ['LOCAL_DEV_USER_TOKEN']}"},
        )
        logger.info(
            f"Append transactions response: {response.status_code} {response.text}"
        )
        assert response.status_code == 200, "Failed to append transactions"

        # 6. Verify the label end point works
        response = client.get(
            API_BASE_URL + "app/v1/transactions/labels",
            headers={"Authorization": f"Bearer {os.environ['LOCAL_DEV_USER_TOKEN']}"},
        )
        logger.info(f"Get labels response: {response.status_code} {response.text}")
        assert response.status_code == 200, "Failed to get labels"
        labels = response.json()
        assert isinstance(labels, dict), "Labels response is not a dict"
