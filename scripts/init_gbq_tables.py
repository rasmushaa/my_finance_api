"""Initialize BigQuery datasets and tables from YAML schema configuration.

Usage
-----
Run from project root:

```
uv run python scripts/init_gbq_tables.py <dev|stg|prod>
```
"""

import os
import sys

from bigquery_table_config import SCHEMA_CONFIG_PATH, load_bigquery_table_definitions
from dotenv import load_dotenv
from google.cloud import bigquery
from google.cloud.exceptions import Conflict


def __build_schema_fields(
    column_specs: list[dict[str, str]]
) -> list[bigquery.SchemaField]:
    """Build BigQuery schema fields from column specs.

    Parameters
    ----------
    column_specs : list[dict[str, str]]
        Ordered list of column definitions from YAML.

    Returns
    -------
    list[bigquery.SchemaField]
        SchemaField list passed to BigQuery table creation.
    """
    schema_fields: list[bigquery.SchemaField] = []
    for col in column_specs:
        schema_fields.append(
            bigquery.SchemaField(
                col["name"],
                col["type"],
                mode=col.get("mode", "NULLABLE"),
                description=col.get("description"),
            )
        )
    return schema_fields


def __create_table(
    dataset: bigquery.Table, table_name: str, schema: list, client: bigquery.Client
) -> None:
    """Create a table and ignore already-existing table conflicts.

    Parameters
    ----------
    dataset : bigquery.Table
        Destination dataset reference.
    table_name : str
        Table name to create inside the dataset.
    schema : list
        BigQuery schema field list.
    client : bigquery.Client
        BigQuery client used for table creation.
    """
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
    """Entrypoint for dataset and table initialization."""

    # 1. Verify User Inputs Env: Dev, Stg, Prod
    if len(sys.argv) != 2 or sys.argv[1] not in ["dev", "stg", "prod"]:
        print("Usage: python scripts/init_gbq_tables.py <dev, stg, prod>")
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

    # 3. Initialize BigQuery client object for creating non-existing datasets/tables
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

    table_definitions = load_bigquery_table_definitions()
    print(
        f"Loaded {len(table_definitions)} table definitions from {SCHEMA_CONFIG_PATH}"
    )

    for table_name, column_specs in table_definitions.items():
        schema = __build_schema_fields(column_specs)
        __create_table(dataset, table_name, schema, client)


if __name__ == "__main__":
    main()
