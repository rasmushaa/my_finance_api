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

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from app.main import app

logger = logging.getLogger(__name__)

# Container needs JWT, which needs environment variables
os.environ["APP_JWT_SECRET"] = "test-secret-key-for-jwt-testing"
os.environ["APP_JWT_EXP_DELTA_MINUTES"] = "60"

subprocess.run(
    ["uv", "run", "python", "scripts/create_local_dev_tokens.py"], check=True
)  # Refresh local dev tokens

API_BASE_URL = "https://localhost:8081/"
MOCK_FILE_NAME = "local-integrtion-mock-data"


@pytest.mark.integration
def test_category_integration():

    with TestClient(app) as client:
        response = client.get(
            API_BASE_URL + "data/categories/expenditures",
            headers={"Authorization": f"Bearer {os.environ['LOCAL_DEV_USER_TOKEN']}"},
        )
        logger.info(f"Categories response: {response.status_code} {response.text}")
        assert response.status_code == 200, "Failed to fetch categories"

        response = client.get(
            API_BASE_URL + "data/categories/assets",
            headers={"Authorization": f"Bearer {os.environ['LOCAL_DEV_USER_TOKEN']}"},
        )
        logger.info(f"Categories response: {response.status_code} {response.text}")
        assert response.status_code == 200, "Failed to fetch categories"


@pytest.mark.integration
def test_transaction_integration():

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
            API_BASE_URL + "io/delete-filetype",
            json={"file_name": MOCK_FILE_NAME},
            headers={"Authorization": f"Bearer {os.environ['LOCAL_DEV_ADMIN_TOKEN']}"},
        )
        logger.info(
            f"Delete file type response: {response.status_code} {response.text}"
        )

        # 2. Create new file type
        response = client.post(
            API_BASE_URL + "io/register-filetype",
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
            API_BASE_URL + "io/transform-csv",
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
            API_BASE_URL + "io/append-transactions",
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
