import os
import sys

from dotenv import load_dotenv
from google.cloud import bigquery
from google.cloud.exceptions import Conflict

# How to run: uv run python scripts/init_gbq_tables.py <name of the environment, dev, stg, prod, etc.>


BASIC_META_COLS = [
    bigquery.SchemaField(
        "_RowStatus",
        "STRING",
        mode="REQUIRED",
        description="Status of the row (i=inserted, u=updated, d=deleted)",
    ),
    bigquery.SchemaField(
        "_RowCreatedAt",
        "TIMESTAMP",
        mode="REQUIRED",
        description="Timestamp when the row was first created",
    ),
    bigquery.SchemaField(
        "_RowUpdatedAt",
        "TIMESTAMP",
        mode="NULLABLE",
        description="Timestamp when the row was last updated",
    ),
    bigquery.SchemaField(
        "_RowUploadHash",
        "STRING",
        mode="NULLABLE",
        description="Original hash of the row data (including the metadata cols) for traceability and auditing purposes",
    ),
]
TRANSACTIONS_META_COLS = [
    bigquery.SchemaField(
        "_RowProcessingID",
        "STRING",
        mode="NULLABLE",
        description="Unique ID (input features and timestamp) to link the original input row to the model predictions for monitoring and auditing purposes",
    ),
]


def __create_table(
    dataset: bigquery.Table, table_name: str, schema: list, client: bigquery.Client
) -> None:
    table = dataset.table(table_name)
    table = bigquery.Table(table, schema=schema)
    try:
        table = client.create_table(table)
    except Conflict:
        print(
            f"Warning: there already exists a '{table_name}' table in the '{dataset.dataset_id}' dataset\nProceeding to next table..."
        )
        return
    print(f"Created table: {table.project}.{table.dataset_id}.{table.table_id}")


def main():

    # 1. Verify User Inputs Env: Dev, Stg, Prod
    if len(sys.argv) != 2 or sys.argv[1] not in ["dev", "stg", "prod"]:
        print("Usage: python init_bigquery_databse.py <dev, stg, prod>")
        sys.exit(1)

    print(f"\nConstructing BigQuery Database for {sys.argv[1]}-environment")

    # 2 Set build configuration
    dotenv_file = f".env"
    if os.path.exists(dotenv_file):
        load_dotenv(dotenv_file)
    else:
        raise ValueError(f"No path: {dotenv_file}")

    project_id = os.getenv("GCP_PROJECT_ID")
    location = os.getenv("GCP_LOCATION")
    dataset_id = os.getenv("GCP_BQ_DATASET") + "_" + sys.argv[1]

    # 3. Initializea BigQuery client object for Creating Non-Existant Databasets/Tables
    client = bigquery.Client()

    # 4. Construct a Dataset object to send to the API.
    dataset = bigquery.Dataset(f"{project_id}.{dataset_id}")
    dataset.location = location
    try:
        dataset = client.create_dataset(dataset, timeout=30)
        print(f"Created dataset: {project_id}.{dataset_id} at {location}")
    except Conflict:
        print(
            f"Warning: there already exists a '{dataset_id}' dataset in the '{project_id}' project\nProceeding to create tables in the existing dataset..."
        )

    # 5. Create Credentials table
    schema = [
        bigquery.SchemaField(
            "UserEmail",
            "STRING",
            mode="REQUIRED",
            description="Google account (OAuth2) email of the user",
        ),
        bigquery.SchemaField(
            "UserRole",
            "STRING",
            mode="REQUIRED",
            description="Role of the user within the application (admin, user)",
        ),
    ] + BASIC_META_COLS
    __create_table(dataset, "d_credentials", schema, client)

    # 6. Create Known Filetypes table
    schema = [
        bigquery.SchemaField(
            "FileID",
            "STRING",
            mode="REQUIRED",
            description="Unique id of the file type, generated as a hash of the column names. Used to match incoming files to their corresponding schema for transformation.",
        ),
        bigquery.SchemaField(
            "FileName", "STRING", mode="REQUIRED", description="Name of the file type"
        ),
        bigquery.SchemaField(
            "DateColumn",
            "STRING",
            mode="REQUIRED",
            description="Name of the column containing the date",
        ),
        bigquery.SchemaField(
            "DateColumnFormat",
            "STRING",
            mode="REQUIRED",
            description="Format of the date column, i.e. how to parse the date values, e.g. %Y-%m-%d",
        ),
        bigquery.SchemaField(
            "AmountColumn",
            "STRING",
            mode="REQUIRED",
            description="Name of the column containing the amount",
        ),
        bigquery.SchemaField(
            "ReceiverColumn",
            "STRING",
            mode="REQUIRED",
            description="Name of the column containing the receiver",
        ),
    ] + BASIC_META_COLS
    __create_table(dataset, "d_filetypes", schema, client)

    # 7. Create the Main Transactions table
    schema = (
        [
            bigquery.SchemaField(
                "UserEmail",
                "STRING",
                mode="REQUIRED",
                description="Google account (OAuth2) email of the user",
            ),
            bigquery.SchemaField(
                "Date", "DATE", mode="REQUIRED", description="Date of the transaction"
            ),
            bigquery.SchemaField(
                "Amount",
                "FLOAT",
                mode="REQUIRED",
                description="Amount of the transaction",
            ),
            bigquery.SchemaField(
                "Receiver",
                "STRING",
                mode="REQUIRED",
                description="Receiver of the transaction",
            ),
            bigquery.SchemaField(
                "Category",
                "STRING",
                mode="REQUIRED",
                description="Category of the transaction",
            ),
        ]
        + TRANSACTIONS_META_COLS
        + BASIC_META_COLS
    )
    __create_table(dataset, "f_transactions", schema, client)

    # 8. Create the Main Assets table
    schema = [
        bigquery.SchemaField(
            "UserEmail",
            "STRING",
            mode="REQUIRED",
            description="Google account (OAuth2) email of the user",
        ),
        bigquery.SchemaField(
            "Date",
            "DATE",
            mode="REQUIRED",
            description="Reporting date of the asset record",
        ),
        bigquery.SchemaField(
            "Category", "STRING", mode="REQUIRED", description="Category of the asset"
        ),
        bigquery.SchemaField(
            "Value", "FLOAT", mode="REQUIRED", description="Value of the asset"
        ),
    ] + BASIC_META_COLS
    __create_table(dataset, "f_assets", schema, client)

    # 9. Create the Predictions monitoring table
    schema = (
        [
            bigquery.SchemaField(
                "PredictedCategory",
                "STRING",
                mode="REQUIRED",
                description="Predicted category of the transaction",
            ),
            bigquery.SchemaField(
                "ModelName",
                "STRING",
                mode="REQUIRED",
                description="Name of the model used for prediction",
            ),
            bigquery.SchemaField(
                "ModelAlias",
                "STRING",
                mode="REQUIRED",
                description="Alias of the model used for prediction",
            ),
            bigquery.SchemaField(
                "ModelVersion",
                "STRING",
                mode="REQUIRED",
                description="Version of the model used for prediction",
            ),
            bigquery.SchemaField(
                "ModelCommitSHA",
                "STRING",
                mode="REQUIRED",
                description="Commit SHA of the model used for prediction",
            ),
            bigquery.SchemaField(
                "ModelArchitecture",
                "STRING",
                mode="REQUIRED",
                description="Architecture of the model used for prediction",
            ),
        ]
        + TRANSACTIONS_META_COLS
        + BASIC_META_COLS
    )
    __create_table(dataset, "f_predictions", schema, client)


if __name__ == "__main__":
    main()
