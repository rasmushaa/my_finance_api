"""These are basic test for Google Cloud API interactions.

They use mocking to avoid real GCP calls, but usefulness is limited since they don't
test actual GCP integration.
"""

import os
from unittest.mock import patch

import pandas as pd
from google.cloud import bigquery

from app.core.database_client import GoogleCloudAPI


@patch.dict(
    os.environ,
    {
        "GCP_PROJECT_ID": "test-project",
        "GCP_BQ_DATASET": "test_dataset",
        "ENV": "prod",
        "GCP_LOCATION": "US",
        "GCP_BUCKET_NAME": "test-bucket",
    },
)
def test_dataset_property_env():
    """Test that dataset property works correctly based on environment variable."""
    api = GoogleCloudAPI()
    assert api.dataset == "test_dataset_prod"


@patch("app.core.database_client.bigquery.Client")
@patch.dict(
    os.environ,
    {
        "GCP_PROJECT_ID": "test-project",
        "GCP_BQ_DATASET": "test_dataset",
        "ENV": "test",
        "GCP_LOCATION": "US",
        "GCP_BUCKET_NAME": "test-bucket",
    },
)
def test_sql_to_pandas_without_params_uses_bigquery_client(mock_bq_client):
    """Non-parameterized reads should still execute via BigQuery client query."""
    # Arrange
    mock_df = pd.DataFrame({"col1": [1, 2], "col2": ["a", "b"]})
    mock_job = mock_bq_client.return_value.query.return_value
    mock_job.to_dataframe.return_value = mock_df

    api = GoogleCloudAPI()
    sql_query = "SELECT * FROM test_table"

    # Act
    result = api.sql_to_pandas(sql_query)

    # Assert
    mock_bq_client.return_value.query.assert_called_once()
    call_args, call_kwargs = mock_bq_client.return_value.query.call_args
    assert call_args[0] == sql_query
    assert call_kwargs["job_config"] is None

    mock_job.to_dataframe.assert_called_once_with(create_bqstorage_client=False)
    pd.testing.assert_frame_equal(result, mock_df)


@patch("pandas_gbq.to_gbq")
@patch.dict(
    os.environ,
    {
        "GCP_PROJECT_ID": "test-project",
        "GCP_BQ_DATASET": "test_dataset",
        "ENV": "test",
        "GCP_LOCATION": "US",
        "GCP_BUCKET_NAME": "test-bucket",
    },
)
def test_append_pandas_to_table_schema(mock_to_gbq):
    """Test append_pandas_to_table builds correct BQ schema for mixed column types."""
    # Arrange
    api = GoogleCloudAPI()
    df = pd.DataFrame(
        {
            "name": ["Alice", "Bob"],
            "city": ["NYC", "LA"],
            "transaction_date": ["2023-01-01", "2023-01-02"],
            "end_date": ["2023-12-31", "2023-12-30"],
            "amount": [100.0, 200.0],
        }
    )
    table_name = "test_table"

    # Act
    api.append_pandas_to_table(df, table_name)

    # Assert
    mock_to_gbq.assert_called_once()
    _, kwargs = mock_to_gbq.call_args

    schema = kwargs["table_schema"]
    schema_by_name = {col["name"]: col["type"] for col in schema}

    assert schema_by_name["name"] == "STRING"
    assert schema_by_name["city"] == "STRING"
    assert schema_by_name["transaction_date"] == "DATE"
    assert schema_by_name["end_date"] == "DATE"

    assert kwargs["destination_table"] == "test_dataset_test.test_table"
    assert kwargs["project_id"] == "test-project"
    assert kwargs["location"] == "US"
    assert kwargs["if_exists"] == "append"


@patch("pandas_gbq.to_gbq")
@patch.dict(
    os.environ,
    {
        "GCP_PROJECT_ID": "test-project",
        "GCP_BQ_DATASET": "test_dataset",
        "ENV": "test",
        "GCP_LOCATION": "US",
        "GCP_BUCKET_NAME": "test-bucket",
    },
)
def test_append_pandas_to_table_includes_metadata_columns(mock_to_gbq):
    """Test that append_pandas_to_table includes metadata columns in the uploaded
    DataFrame."""
    api = GoogleCloudAPI()
    df = pd.DataFrame({"amount": [10.0, 20.0], "name": ["Alice", "Bob"]})

    api.append_pandas_to_table(df, "test_table")

    mock_to_gbq.assert_called_once()
    args, _ = mock_to_gbq.call_args
    uploaded_df = args[0]

    # Metadata columns are present
    assert "_RowStatus" in uploaded_df.columns
    assert "_RowCreatedAt" in uploaded_df.columns
    assert "_RowUpdatedAt" in uploaded_df.columns
    assert "_RowUploadHash" in uploaded_df.columns

    # Original data is preserved
    assert list(uploaded_df["amount"]) == [10.0, 20.0]
    assert list(uploaded_df["name"]) == ["Alice", "Bob"]

    # _RowStatus is always 'i' (inserted)
    assert (uploaded_df["_RowStatus"] == "i").all()

    # Timestamps are pandas Timestamps
    assert pd.api.types.is_datetime64_any_dtype(uploaded_df["_RowCreatedAt"])
    assert pd.api.types.is_datetime64_any_dtype(uploaded_df["_RowUpdatedAt"])

    # CreatedAt and UpdatedAt are equal on insert
    assert (uploaded_df["_RowCreatedAt"] == uploaded_df["_RowUpdatedAt"]).all()

    # Hash values are positive integers and unique per row
    assert (
        uploaded_df["_RowUploadHash"]
        .apply(lambda x: isinstance(x, int) and x > 0)
        .all()
    )
    assert uploaded_df["_RowUploadHash"].nunique() == len(uploaded_df)

    # Original DataFrame is not mutated
    assert "_RowStatus" not in df.columns


@patch("app.core.database_client.bigquery.Client")
@patch.dict(
    os.environ,
    {
        "GCP_PROJECT_ID": "test-project",
        "GCP_BQ_DATASET": "test_dataset",
        "ENV": "test",
        "GCP_LOCATION": "US",
        "GCP_BUCKET_NAME": "test-bucket",
    },
)
def test_sql_to_pandas_uses_query_parameters_with_bigquery_client(mock_bq_client):
    """Parameterized reads should use BigQuery client query with QueryJobConfig."""
    mock_df = pd.DataFrame({"latest_date": ["2024-01-01"]})

    mock_job = mock_bq_client.return_value.query.return_value
    mock_job.to_dataframe.return_value = mock_df

    api = GoogleCloudAPI()
    result = api.sql_to_pandas(
        "SELECT @user_email as u",
        params={"user_email": "user@example.com"},
    )

    assert result.equals(mock_df)
    mock_bq_client.return_value.query.assert_called_once()
    _, kwargs = mock_bq_client.return_value.query.call_args
    assert isinstance(kwargs["job_config"], bigquery.QueryJobConfig)
    qps = kwargs["job_config"].query_parameters
    assert len(qps) == 1
    assert qps[0].name == "user_email"
    assert qps[0].type_ == "STRING"


@patch("app.core.database_client.bigquery.Client")
@patch.dict(
    os.environ,
    {
        "GCP_PROJECT_ID": "test-project",
        "GCP_BQ_DATASET": "test_dataset",
        "ENV": "test",
        "GCP_LOCATION": "US",
        "GCP_BUCKET_NAME": "test-bucket",
    },
)
def test_execute_sql_uses_query_parameters_with_bigquery_client(mock_bq_client):
    """Parameterized execute_sql should send QueryJobConfig to BigQuery query."""
    mock_job = mock_bq_client.return_value.query.return_value
    mock_job.num_dml_affected_rows = 2

    api = GoogleCloudAPI()
    affected = api.execute_sql(
        "UPDATE t SET x=1 WHERE UserEmail = @user_email",
        params={"user_email": "user@example.com"},
    )

    assert affected == 2
    mock_bq_client.return_value.query.assert_called_once()
    _, kwargs = mock_bq_client.return_value.query.call_args
    assert isinstance(kwargs["job_config"], bigquery.QueryJobConfig)
    qps = kwargs["job_config"].query_parameters
    assert len(qps) == 1
    assert qps[0].name == "user_email"
    assert qps[0].type_ == "STRING"
