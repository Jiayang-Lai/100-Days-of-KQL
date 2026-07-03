"""Execute a KQL query against the local Kusto emulator.

This script provides a minimal harness for running queries against the
local Kustainer instance used by this repository.
"""

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Literal, cast

from app_logger import add_log_mode_argument, build_app_logger
from azure.kusto.data import (
  ClientRequestProperties,
  KustoClient,
  KustoConnectionStringBuilder,
)
from pydantic import BaseModel

DEFAULT_KUSTO_URI = "http://localhost:8080"
DEFAULT_DATABASE = "NetDefaultDB"
SCHEMAS_DIR = Path(__file__).parent.parent / "schemas" / "tables"
APP_LOGGER = build_app_logger("execute_kql_query")
SCHEMA_REFERENCE = (
  "https://github.com/Jiayang-Lai/100-Days-of-KQL/raw/refs/heads/main/"
  "schemas/files/table.json"
)

SchemaColumnType = Literal[
  "bool",
  "datetime",
  "decimal",
  "dynamic",
  "guid",
  "int",
  "long",
  "real",
  "string",
  "timespan",
]


class QueryResultTable(BaseModel):
  """Structured representation of a query result table."""

  columns: dict[str, str]
  rows: list[dict[str, Any]]
  row_count: int


class QueryExecutionResult(BaseModel):
  """Structured representation of a query execution result."""

  database: str
  uri: str
  query: str
  tables: list[QueryResultTable]


class TableSchemaColumn(BaseModel):
  """Column entry for a table schema definition."""

  name: str
  type: SchemaColumnType
  description: str


class TableSchemaDump(BaseModel):
  """Schema dump that follows schemas/files/table.json."""

  table_name: str
  table_description: str
  reference: str
  columns: list[TableSchemaColumn]


def is_valid_kusto_table_name(table_name: str) -> bool:
  """Validate a Kusto table name before using it in a generated query."""
  if not table_name:
    return False

  return re.fullmatch(r"[A-Za-z0-9_]{1,1024}", table_name) is not None


def build_default_query(table_name: str, limit: int) -> str:
  """Build a minimal query for the requested table."""
  if not is_valid_kusto_table_name(table_name):
    raise ValueError(f"Invalid Kusto table name: {table_name}")

  if limit == -1:
    return table_name

  return f"{table_name} | take {limit}"


def build_kusto_client(uri: str) -> Any:
  """Build a Kusto client for the provided URI."""
  kcsb = KustoConnectionStringBuilder.with_aad_application_token_authentication(
    connection_string=uri,
    application_token="justafiller",
  )
  return KustoClient(kcsb)


def normalize_column_type(column_type: str) -> SchemaColumnType:
  """Normalize Kusto column types to the local schema enum values."""
  normalized = column_type.lower()
  type_mapping: dict[str, SchemaColumnType] = {
    "boolean": "bool",
    "datetime": "datetime",
    "decimal": "decimal",
    "dynamic": "dynamic",
    "guid": "guid",
    "int": "int",
    "int32": "int",
    "int64": "long",
    "long": "long",
    "real": "real",
    "string": "string",
    "timespan": "timespan",
  }
  return type_mapping.get(normalized, cast(SchemaColumnType, "string"))


def load_local_table_schema(table_name: str) -> dict[str, Any] | None:
  """Load the local schema definition file for a table if it exists."""
  schema_path = SCHEMAS_DIR / f"{table_name}.json"
  if not schema_path.exists():
    return None

  return json.loads(schema_path.read_text(encoding="utf-8"))


def extract_result_row(result_table: Any, row_index: int = 0) -> dict[str, Any]:
  """Extract a result row as a column-name keyed dictionary."""
  row = result_table[row_index]
  return {
    column.column_name: row[index] for index, column in enumerate(result_table.columns)
  }


def get_first_present(mapping: dict[str, Any], keys: tuple[str, ...]) -> Any:
  """Return the first present value from a mapping for the provided keys."""
  for key in keys:
    if key in mapping:
      return mapping[key]
  return None


def build_schema_dump(
  table_name: str,
  *,
  database: str = DEFAULT_DATABASE,
  uri: str = DEFAULT_KUSTO_URI,
) -> TableSchemaDump:
  """Return a schema dump that follows schemas/files/table.json."""
  if not is_valid_kusto_table_name(table_name):
    raise ValueError(f"Invalid Kusto table name: {table_name}")

  local_schema = load_local_table_schema(table_name) or {}
  local_columns = {column["name"]: column for column in local_schema.get("columns", [])}

  schema_query = f".show table {table_name} schema as json"
  with build_kusto_client(uri) as client:
    response = client.execute_mgmt(database, schema_query)
    result_table = response.primary_results[0]
    if len(result_table) == 0:
      raise RuntimeError(f"No schema returned for table: {table_name}")

    row = extract_result_row(result_table)
    schema_payload = get_first_present(
      row,
      ("Schema", "schema", "TableSchema", "table_schema"),
    )

  if isinstance(schema_payload, str):
    schema_payload = json.loads(schema_payload)
  if not isinstance(schema_payload, dict):
    raise RuntimeError(f"Unexpected schema payload for table: {table_name}")

  payload_columns = get_first_present(
    schema_payload,
    ("OrderedColumns", "orderedColumns", "columns"),
  )
  if not isinstance(payload_columns, list):
    raise RuntimeError(f"Unexpected column payload for table: {table_name}")

  columns: list[TableSchemaColumn] = []
  for column in payload_columns:
    if not isinstance(column, dict):
      continue

    column_name = get_first_present(
      column,
      ("Name", "ColumnName", "name"),
    )
    if not isinstance(column_name, str):
      continue

    column_type = get_first_present(
      column,
      ("CslType", "ColumnType", "Type", "type"),
    )
    if not isinstance(column_type, str):
      column_type = "string"

    local_column = local_columns.get(column_name, {})
    description = get_first_present(
      column,
      ("DocString", "Description", "description"),
    )
    if not isinstance(description, str) or not description:
      description = local_column.get("description", "")

    columns.append(
      TableSchemaColumn(
        name=column_name,
        type=normalize_column_type(column_type),
        description=description,
      )
    )

  table_description = get_first_present(
    schema_payload,
    ("DocString", "Description", "table_description"),
  )
  if not isinstance(table_description, str) or not table_description:
    table_description = local_schema.get("table_description", "")

  reference = local_schema.get("reference", SCHEMA_REFERENCE)
  if not isinstance(reference, str) or not reference:
    reference = SCHEMA_REFERENCE

  return TableSchemaDump(
    table_name=local_schema.get("table_name", table_name),
    table_description=table_description,
    reference=reference,
    columns=columns,
  )


def result_table_to_schema(result_table: Any) -> dict[str, str]:
  """Convert a Kusto result table schema into a name-to-type mapping."""
  return {
    column.column_name: str(column.column_type) for column in result_table.columns
  }


def result_table_to_rows(result_table: Any) -> list[dict[str, Any]]:
  """Convert a Kusto result table into JSON-serializable rows."""
  columns = list(result_table_to_schema(result_table))
  rows: list[dict[str, Any]] = []

  for row in result_table.rows:
    row_dict = {}
    for index, value in enumerate(row):
      if hasattr(value, "isoformat"):
        row_dict[columns[index]] = value.isoformat()
      else:
        row_dict[columns[index]] = value
    rows.append(row_dict)

  return rows


def execute_query(
  query: str,
  *,
  database: str = DEFAULT_DATABASE,
  uri: str = DEFAULT_KUSTO_URI,
  query_now: str | None = None,
) -> QueryExecutionResult:
  """Execute a KQL query and return a JSON-serializable result."""
  properties = ClientRequestProperties()
  if query_now:
    properties.set_option("query_now", query_now)

  with build_kusto_client(uri) as client:
    response = client.execute(database, query, properties)
    primary_results = response.primary_results

    tables: list[QueryResultTable] = []
    for table in primary_results:
      tables.append(
        QueryResultTable(
          columns=result_table_to_schema(table),
          rows=result_table_to_rows(table),
          row_count=len(table),
        )
      )

  return QueryExecutionResult(
    database=database,
    uri=uri,
    query=query,
    tables=tables,
  )


def print_query_execution_summary(result: QueryExecutionResult) -> None:
  """Print an aggregated summary of query execution results to stderr."""
  total_rows = sum(table.row_count for table in result.tables)
  APP_LOGGER.info(
    (f"[Execution Summary] {len(result.tables)} table(s), {total_rows} total row(s)"),
    stderr=True,
  )

  for index, table in enumerate(result.tables, start=1):
    column_names = list(table.columns)
    preview_columns = ", ".join(column_names[:5])
    if len(column_names) > 5:
      preview_columns = f"{preview_columns}, ..."

    APP_LOGGER.info(
      (f"  Table {index}: {table.row_count} row(s), {len(column_names)} column(s)"),
      stderr=True,
    )
    if preview_columns:
      APP_LOGGER.info(f"    Columns: {preview_columns}", stderr=True)


def main() -> None:
  """Parse arguments and execute a KQL query."""
  parser = argparse.ArgumentParser(
    description="Execute a KQL query against the local Kusto emulator"
  )
  add_log_mode_argument(parser)
  parser.add_argument(
    "--table",
    help=(
      "Table name to use when the script needs one explicitly. Required for "
      "--schema-dump. Optional for query execution, where it is only used if "
      "--query is omitted and the script must generate a query for you."
    ),
  )
  parser.add_argument(
    "--query",
    help=(
      "Raw KQL query to execute as-is. If you provide this, you usually do not "
      "need --table because the table reference should already be inside the query. "
      "--limit is ignored when --query is used."
    ),
  )
  parser.add_argument(
    "--limit",
    type=int,
    default=10,
    help=(
      "Only used when the script generates a query from --table because --query "
      "was not provided (default: 10). Use -1 to generate just '<table>' with "
      "no '| take ...'. Ignored when --query is provided."
    ),
  )
  parser.add_argument(
    "--database",
    default=DEFAULT_DATABASE,
    help=(
      f"Kusto database to run the query or schema lookup against "
      f"(default: {DEFAULT_DATABASE})."
    ),
  )
  parser.add_argument(
    "--uri",
    default=DEFAULT_KUSTO_URI,
    help=f"Kusto engine endpoint URI (default: {DEFAULT_KUSTO_URI}).",
  )
  parser.add_argument(
    "--query-now",
    dest="query_now",
    help=(
      "Optional ISO-8601 timestamp for Kusto's query_now setting. Useful when "
      "you want deterministic results from time-based queries."
    ),
  )
  parser.add_argument(
    "--schema-dump",
    action="store_true",
    help=(
      "Return the specified table schema as JSON in the local "
      "schemas/files/table.json-compatible format. Requires --table."
    ),
  )
  args = parser.parse_args()
  APP_LOGGER.set_mode(args.log_mode)

  try:
    if args.schema_dump:
      if not args.table:
        parser.error("--schema-dump requires --table.")
      if args.query:
        parser.error("--schema-dump cannot be used with --query.")
      result = build_schema_dump(
        args.table,
        database=args.database,
        uri=args.uri,
      )
    else:
      query = args.query
      if not query:
        if not args.table:
          parser.error("Provide either --query or --table.")
        query = build_default_query(args.table, args.limit)

      result = execute_query(
        query,
        database=args.database,
        uri=args.uri,
        query_now=args.query_now,
      )
  except Exception as exc:
    APP_LOGGER.error(f"Error: {exc}")
    sys.exit(1)

  if isinstance(result, QueryExecutionResult):
    print_query_execution_summary(result)

  print(result.model_dump_json(indent=2))


if __name__ == "__main__":
  main()
