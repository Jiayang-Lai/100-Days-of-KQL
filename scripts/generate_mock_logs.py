"""Generate schema-aligned mock logs from IOC context using Kusto MCP tools.

This script uses a chat model plus the local Kusto MCP server to inspect
available table schemas and generate realistic mock Microsoft Sentinel rows for
the tables the user explicitly allows or, when none are specified, the tables
the agent selects from the local schema catalog. The IOC context can be
provided inline or loaded from a document, and the agent returns structured
output grouped by table so the result can be used for testing or automation.

By default, the structured JSON response is printed to stdout. When file output
is enabled, the script instead writes a bundle under `samples/generated_mock_logs`
that includes the raw JSON response, one CSV per generated table, and
optionally a `bootstrap.kql` file with `externaldata(...)` statements that can
be used to load the generated CSVs into Kusto through the local Caddy-backed
file server.
"""

import argparse
import asyncio
import csv
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, TypedDict, cast

from agent_output import collect_token_usage, print_agent_events
from app_logger import LogMode, add_log_mode_argument, build_app_logger
from dotenv import load_dotenv
from fastmcp import Client
from kusto_mcp import FileSchemaLoader, configure_loader, mcp
from kusto_mcp.server import list_tables as mcp_list_tables
from langchain.agents import create_agent
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_mcp_adapters.client import MultiServerMCPClient
from model_factory import (
  DEFAULT_MODEL_NAME,
  DEFAULT_MODEL_PROVIDER,
  create_chat_model,
)
from pydantic import BaseModel, Field

load_dotenv()

# Schema directory relative to this script
SCHEMAS_DIR = Path(__file__).parent.parent / "schemas" / "tables"
SAMPLES_DIR = Path(__file__).parent.parent / "samples"
GENERATED_SAMPLES_DIR = SAMPLES_DIR / "generated_mock_logs"
SYSTEM_PROMPT_PATH = Path(__file__).parent / "prompts" / "mock_log.prompt.md"

# Configure the MCP server to use our local schema directory
configure_loader(FileSchemaLoader(schemas_dir=SCHEMAS_DIR))

# Load system prompt from markdown file
SYSTEM_PROMPT = SYSTEM_PROMPT_PATH.read_text(encoding="utf-8")
APP_LOGGER = build_app_logger("generate_mock_logs")


class MockLogTable(BaseModel):
  """Mock rows generated for a single table."""

  table_name: str
  purpose: str
  rows: list[dict[str, Any]] = Field(default_factory=list)


class MockLogResult(BaseModel):
  """Structured output for mock log generation."""

  request: str
  ioc_summary: str
  tables_used: list[str]
  mock_logs: list[MockLogTable]
  explanation: str
  token_usage: dict[str, int] | None = None


class AgentResponse(TypedDict):
  """Subset of the agent response used by this script."""

  messages: list[Any]
  structured_response: MockLogResult


class Args(argparse.Namespace):
  """Command-line arguments for this script."""

  bootstrap_base_url: str
  ioc_text: str | None
  ioc_file: Path | None
  list_tables: bool
  log_mode: LogMode
  model: str
  model_provider: str
  output_name: str | None
  table: list[str]
  rows_per_table: int
  verbose: bool
  write_bootstrap_kql: bool
  write_files: bool


def sanitize_path_component(value: str) -> str:
  """Convert a user-facing name into a filesystem-safe path component."""
  sanitized = "".join(char.lower() if char.isalnum() else "-" for char in value.strip())
  sanitized = "-".join(part for part in sanitized.split("-") if part)
  return sanitized or "mock-logs"


def csv_safe_value(value: Any) -> str | int | float | bool:
  """Convert nested JSON values into CSV-safe scalar values."""
  if value is None:
    return ""

  if isinstance(value, (str, int, float, bool)):
    return value

  return json.dumps(value, separators=(",", ":"), sort_keys=True)


def collect_csv_columns(rows: list[dict[str, Any]]) -> list[str]:
  """Collect CSV column names in first-seen order across all rows."""
  columns: list[str] = []
  seen: set[str] = set()

  for row in rows:
    for column in row:
      if column not in seen:
        seen.add(column)
        columns.append(column)

  return columns


def load_table_schema(table_name: str) -> dict[str, str]:
  """Load the local schema type mapping for a table."""
  schema_path = SCHEMAS_DIR / f"{table_name}.json"
  if not schema_path.exists():
    return {}

  schema = json.loads(schema_path.read_text(encoding="utf-8"))
  columns = schema.get("columns", [])
  if not isinstance(columns, list):
    return {}

  schema_map: dict[str, str] = {}
  for column in columns:
    if not isinstance(column, dict):
      continue
    name = column.get("name")
    column_type = column.get("type")
    if isinstance(name, str) and isinstance(column_type, str):
      schema_map[name] = column_type

  return schema_map


def build_externaldata_schema(table: MockLogTable) -> str:
  """Build the externaldata column schema for a generated CSV."""
  schema_map = load_table_schema(table.table_name)
  columns = collect_csv_columns(table.rows)

  rendered_columns = [
    f"    {column}:{schema_map.get(column, 'string')}" for column in columns
  ]
  return ",\n".join(rendered_columns)


def join_url(base_url: str, relative_path: str) -> str:
  """Join a base URL and relative path without duplicate slashes."""
  return f"{base_url.rstrip('/')}/{relative_path.lstrip('/')}"


def build_bootstrap_kql(
  result: MockLogResult,
  *,
  bundle_dir: Path,
  bootstrap_base_url: str,
) -> str:
  """Build bootstrap KQL to load generated CSVs through externaldata."""
  relative_bundle_dir = bundle_dir.relative_to(SAMPLES_DIR)
  statements: list[str] = []

  for table in result.mock_logs:
    csv_name = f"{sanitize_path_component(table.table_name)}.csv"
    csv_relative_path = relative_bundle_dir / csv_name
    csv_url = join_url(
      bootstrap_base_url,
      csv_relative_path.as_posix(),
    )
    schema_block = build_externaldata_schema(table)
    statements.append(
      f"let {table.table_name} = externaldata(\n"
      f"{schema_block}\n"
      f')\n["{csv_url}"]\n'
      'with(format="csv", ignoreFirstRecord=true);'
    )

  return "\n".join(statements)


def write_table_csv(table: MockLogTable, output_path: Path) -> None:
  """Write a single table's mock rows to CSV."""
  columns = collect_csv_columns(table.rows)

  with output_path.open("w", encoding="utf-8", newline="") as file_handle:
    writer = csv.DictWriter(file_handle, fieldnames=columns)
    writer.writeheader()
    for row in table.rows:
      writer.writerow({column: csv_safe_value(row.get(column)) for column in columns})


def write_output_bundle(
  result: MockLogResult,
  *,
  bootstrap_base_url: str,
  output_name: str | None,
  write_bootstrap_kql: bool,
) -> Path:
  """Write raw JSON and CSV artifacts under samples/ for ingestion."""
  bundle_name = output_name
  if bundle_name is None:
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    bundle_name = f"mock-logs-{timestamp}"

  bundle_dir = GENERATED_SAMPLES_DIR / sanitize_path_component(bundle_name)
  bundle_dir.mkdir(parents=True, exist_ok=True)

  raw_json_path = bundle_dir / "mock_logs.raw.json"
  raw_json_path.write_text(result.model_dump_json(indent=2), encoding="utf-8")

  for table in result.mock_logs:
    csv_path = bundle_dir / f"{sanitize_path_component(table.table_name)}.csv"
    write_table_csv(table, csv_path)

  if write_bootstrap_kql:
    bootstrap_path = bundle_dir / "bootstrap.kql"
    bootstrap_kql = build_bootstrap_kql(
      result,
      bundle_dir=bundle_dir,
      bootstrap_base_url=bootstrap_base_url,
    )
    bootstrap_path.write_text(bootstrap_kql, encoding="utf-8")

  return bundle_dir


def build_user_request(
  *,
  tables: list[str],
  ioc_text: str,
  rows_per_table: int,
  tables_are_user_selected: bool,
) -> str:
  """Build the user request passed to the agent."""
  table_list = ", ".join(tables)
  table_heading = (
    f"Allowed tables: {table_list}"
    if tables_are_user_selected
    else f"Available tables: {table_list}"
  )
  selection_requirement = (
    "- Use only the allowed tables listed above.\n"
    if tables_are_user_selected
    else "- Select the most suitable tables from the available tables listed above.\n"
  )
  return (
    "Generate mock Microsoft Sentinel logs from the IOC context below.\n\n"
    f"{table_heading}\n"
    f"Target rows per selected table: {rows_per_table}\n\n"
    "Requirements:\n"
    f"{selection_requirement}"
    "- Inspect each selected table schema before generating rows.\n"
    "- Only include tables that meaningfully fit the IOC scenario.\n"
    "- Return a structured response with realistic mock rows grouped by table.\n"
    "- Keep rows internally consistent across tables when possible.\n\n"
    "IOC context:\n"
    f"{ioc_text}"
  )


async def run_agent(
  user_request: str,
  *,
  model_provider: str,
  model_name: str,
  verbose: bool = False,
) -> MockLogResult:
  """Run the agent to generate mock logs."""
  model = create_chat_model(provider=model_provider, model_name=model_name)

  client = MultiServerMCPClient(
    {
      "kusto tables": {
        "transport": "stdio",
        "command": "python",
        "args": ["scripts/start_mcp_server.py"],
      }
    }
  )

  tools = await client.get_tools()
  agent = create_agent(model, tools, response_format=MockLogResult)

  messages = [
    SystemMessage(content=SYSTEM_PROMPT),
    HumanMessage(content=user_request),
  ]

  result = cast(AgentResponse, await agent.ainvoke({"messages": messages}))

  if verbose:
    print_agent_events(result["messages"], stream=sys.stderr)

  total_input_tokens, total_output_tokens = collect_token_usage(result["messages"])

  total_tokens = total_input_tokens + total_output_tokens
  token_msg = (
    f"[Tokens: {total_input_tokens} input + {total_output_tokens} output = "
    f"{total_tokens} total]"
  )
  APP_LOGGER.info(token_msg, stderr=True)
  structured_response = result["structured_response"]
  structured_response.token_usage = {
    "input": total_input_tokens,
    "output": total_output_tokens,
    "total": total_tokens,
  }
  return structured_response


def load_ioc_text(args: Args) -> str:
  """Load IOC text from file or inline argument."""
  if args.ioc_file is not None:
    if not args.ioc_file.exists():
      APP_LOGGER.error(f"IOC file not found: {args.ioc_file}")
      sys.exit(2)

    ioc_text = args.ioc_file.read_text(encoding="utf-8").strip()
    if not ioc_text:
      APP_LOGGER.error(f"IOC file is empty: {args.ioc_file}")
      sys.exit(2)
    return ioc_text

  if args.ioc_text is None or not args.ioc_text.strip():
    APP_LOGGER.error("Provide IOC text or use --ioc-file.")
    sys.exit(2)

  return args.ioc_text.strip()


def load_available_tables() -> list[str]:
  """Load the available table names from the local Kusto MCP server."""
  raw_result = mcp_list_tables()

  try:
    parsed_result = json.loads(raw_result)
  except json.JSONDecodeError as exc:
    raise ValueError("Unable to parse kusto-mcp list_tables output.") from exc

  if not isinstance(parsed_result, list):
    raise ValueError("kusto-mcp list_tables returned an unexpected payload.")

  table_names: list[str] = []
  for item in parsed_result:
    if not isinstance(item, dict):
      continue
    table_name = item.get("name")
    if isinstance(table_name, str) and table_name:
      table_names.append(table_name)

  return table_names


async def async_main(args: Args) -> None:
  """Async main entry point."""
  if args.list_tables:
    client = Client(mcp)
    async with client:
      result = await client.call_tool("list_tables", {})
      print(result)
    return

  if args.rows_per_table < 1:
    APP_LOGGER.error("--rows-per-table must be at least 1.")
    sys.exit(2)

  if args.write_bootstrap_kql:
    args.write_files = True

  ioc_text = load_ioc_text(args)
  selected_tables = args.table
  tables_are_user_selected = bool(selected_tables)
  if not selected_tables:
    try:
      selected_tables = load_available_tables()
    except ValueError as exc:
      APP_LOGGER.error(f"Unable to load available tables: {exc}")
      sys.exit(2)

    if not selected_tables:
      APP_LOGGER.error("No tables were returned by kusto-mcp list_tables.")
      sys.exit(2)

    APP_LOGGER.info(
      (
        "No tables were specified; loaded all available tables from "
        "kusto-mcp and will let the agent choose the suitable ones."
      ),
      stderr=True,
    )

  user_request = build_user_request(
    tables=selected_tables,
    ioc_text=ioc_text,
    rows_per_table=args.rows_per_table,
    tables_are_user_selected=tables_are_user_selected,
  )

  APP_LOGGER.info("Running agent to generate mock logs...", stderr=True)
  try:
    result = await run_agent(
      user_request,
      model_provider=args.model_provider,
      model_name=args.model,
      verbose=args.verbose,
    )
    if args.write_files:
      bundle_dir = write_output_bundle(
        result,
        bootstrap_base_url=args.bootstrap_base_url,
        output_name=args.output_name,
        write_bootstrap_kql=args.write_bootstrap_kql,
      )
      APP_LOGGER.info(f"Wrote mock log bundle to: {bundle_dir}", stderr=True)
    else:
      print(result.model_dump_json(indent=2))
  except Exception as e:
    APP_LOGGER.error(f"Error: {e}")
    sys.exit(1)


def main() -> None:
  """Run the mock log generator."""
  parser = argparse.ArgumentParser(
    description="Generate mock Sentinel logs using an LLM agent with Kusto MCP tools"
  )
  add_log_mode_argument(parser)
  parser.add_argument(
    "ioc_text",
    nargs="?",
    help="IOC context as inline text (optional when --ioc-file is used)",
  )
  parser.add_argument(
    "--ioc-file",
    type=Path,
    help="Read IOC context from a file",
  )
  parser.add_argument(
    "--table",
    action="append",
    default=[],
    help=(
      "Table to allow for mock log generation. Repeat for multiple tables. "
      "If omitted, the script loads all available tables from kusto-mcp "
      "and lets the agent choose the suitable ones."
    ),
  )
  parser.add_argument(
    "--rows-per-table",
    type=int,
    default=3,
    help="Target number of mock rows per selected table (default: 3)",
  )
  parser.add_argument(
    "--model-provider",
    default=DEFAULT_MODEL_PROVIDER,
    help=f"Model provider to use for the agent (default: {DEFAULT_MODEL_PROVIDER})",
  )
  parser.add_argument(
    "--model",
    default=DEFAULT_MODEL_NAME,
    help=f"Model name to use for the agent (default: {DEFAULT_MODEL_NAME})",
  )
  parser.add_argument(
    "--write-files",
    action="store_true",
    help=(
      "Write a bundle under samples/generated_mock_logs containing the raw "
      "JSON response and one CSV per generated table. When this flag is set, "
      "the structured JSON is written to disk instead of printed to stdout."
    ),
  )
  parser.add_argument(
    "--output-name",
    help=(
      "Optional folder name for the generated bundle under samples/generated_mock_logs"
    ),
  )
  parser.add_argument(
    "--write-bootstrap-kql",
    action="store_true",
    help=(
      "When writing files, also create bootstrap.kql with externaldata "
      "statements for the generated CSVs. If this flag is set without "
      "--write-files, file writing is enabled automatically."
    ),
  )
  parser.add_argument(
    "--bootstrap-base-url",
    default="https://caddy",
    help=(
      "Base URL used by generated bootstrap.kql for the CSV files "
      "(default: https://caddy)"
    ),
  )
  parser.add_argument(
    "--list-tables",
    action="store_true",
    help="List available tables and exit",
  )
  parser.add_argument(
    "-v",
    "--verbose",
    action="store_true",
    help="Print verbose AI messages to stderr",
  )
  args = parser.parse_args(namespace=Args())
  APP_LOGGER.set_mode(args.log_mode)
  asyncio.run(async_main(args))


if __name__ == "__main__":
  main()
