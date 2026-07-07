"""Run a prompt-driven loop for mock-log generation and KQL validation.

This module orchestrates the end-to-end workflow used to test prompt-driven
detection engineering against generated sample data. The loop:

1. Selects the most relevant Kusto tables for the prompt.
2. Generates mock Microsoft Sentinel logs for those tables.
3. Writes a sample bundle with CSV files and bootstrap KQL.
4. Generates candidate KQL queries.
5. Executes those queries against the generated mock logs.
6. Evaluates the results and refines the request until it succeeds or the
   maximum iteration count is reached.
"""

import argparse
import asyncio
import io
import json
import sys
from contextlib import redirect_stderr
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, TypedDict, cast

from agent_output import collect_token_usage, print_agent_events
from app_logger import LogMode, add_log_mode_argument, build_app_logger
from dotenv import load_dotenv
from execute_kql_query import (
  QueryExecutionResult,
  execute_query,
  print_query_execution_summary,
)
from generate_kql_query import KQLQueryResult
from generate_kql_query import run_agent as run_kql_agent
from generate_mock_logs import (
  MockLogResult,
  write_output_bundle,
)
from generate_mock_logs import (
  build_user_request as build_mock_log_request,
)
from generate_mock_logs import (
  run_agent as run_mock_log_agent,
)
from langchain.agents import create_agent
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain_mcp_adapters.sessions import Connection
from model_factory import (
  DEFAULT_ANTHROPIC_MODEL_NAME,
  DEFAULT_MODEL_PROVIDER,
  create_chat_model,
)
from pydantic import BaseModel, Field

load_dotenv()

TABLE_SELECTION_PROMPT_PATH = (
  Path(__file__).parent / "prompts" / "agent_loop_table_selection.prompt.md"
)
EVALUATION_PROMPT_PATH = (
  Path(__file__).parent / "prompts" / "agent_loop_evaluation.prompt.md"
)
TABLE_SELECTION_SYSTEM_PROMPT = TABLE_SELECTION_PROMPT_PATH.read_text(encoding="utf-8")
EVALUATION_SYSTEM_PROMPT = EVALUATION_PROMPT_PATH.read_text(encoding="utf-8")
MCP_SERVER_CONFIG: dict[str, Connection] = {
  "kusto tables": {
    "transport": "stdio",
    "command": "python",
    "args": ["scripts/start_mcp_server.py"],
  }
}
APP_LOGGER = build_app_logger("run_detection_agent_loop")
REPO_ROOT = Path(__file__).parent.parent.resolve()


class TableSelectionResult(BaseModel):
  """Selected tables for the detection-validation workflow."""

  request: str
  tables: list[str]
  rationale: str
  token_usage: dict[str, int] | None = None


class QueryCandidateExecution(BaseModel):
  """Execution result for one generated KQL candidate."""

  candidate_index: int
  query: str
  success: bool
  total_rows: int
  error: str | None = None
  execution_result: QueryExecutionResult | None = None


class IterationEvaluationResult(BaseModel):
  """Evaluation outcome for a single refinement iteration."""

  criteria_met: bool
  best_query_index: int | None = None
  feedback: str
  refined_request: str
  token_usage: dict[str, int] | None = None


class LoopIterationRecord(BaseModel):
  """Persisted details for one loop iteration."""

  iteration: int
  request: str
  generated_queries: list[str]
  kql_generation_token_usage: dict[str, int] | None = None
  candidate_executions: list[QueryCandidateExecution]
  evaluation: IterationEvaluationResult


class DetectionAgentLoopResult(BaseModel):
  """Structured result of the end-to-end loop."""

  prompt_file: str
  bundle_dir: str
  bootstrap_kql_path: str
  log_path: str
  result_path: str
  tables_selected: list[str]
  criteria_met: bool
  table_selection_token_usage: dict[str, int] | None = None
  mock_log_token_usage: dict[str, int] | None = None
  total_token_usage: dict[str, int] | None = None
  query_now: str | None = None
  final_iteration: int | None = None
  final_query: str | None = None
  final_query_index: int | None = None
  iterations: list[LoopIterationRecord] = Field(default_factory=list)


class AgentResponse(TypedDict):
  """Subset of the agent response used by this script."""

  messages: list[Any]
  structured_response: TableSelectionResult | IterationEvaluationResult


class Args(argparse.Namespace):
  """Command-line arguments for this script."""

  bootstrap_base_url: str
  log_mode: LogMode
  max_iterations: int
  model: str
  model_provider: str
  output_name: str | None
  prompt_file: Path
  redact_paths: bool
  reuse_mock_log_bundle: Path | None
  rows_per_table: int
  verbose: bool


def log_line(message: str, *, log_path: Path | None = None) -> None:
  """Emit a message and optionally append it to the loop log.

  Args:
    message: Message text to emit and optionally persist.
    log_path: Optional path to the loop log file.
  """
  emit_log_message(message)
  append_log_text(f"{message}\n", log_path=log_path)


def write_log_block(text: str, *, log_path: Path | None = None) -> None:
  """Emit a multiline block and optionally append it to the loop log.

  Args:
    text: Multiline text block to emit.
    log_path: Optional path to the loop log file.
  """
  if not text:
    return

  text = text.rstrip()
  emit_log_message(text)
  append_log_text(f"{text}\n", log_path=log_path)


def emit_log_message(message: str) -> None:
  """Emit a user-facing log message through the shared app logger.

  Args:
    message: Message text to emit.
  """
  APP_LOGGER.info(message, stderr=True)


def append_log_text(text: str, *, log_path: Path | None = None) -> None:
  """Append text to the loop log file when a path is provided.

  Args:
    text: Text to append as-is.
    log_path: Optional path to the loop log file.
  """
  if log_path is None:
    return

  with log_path.open("a", encoding="utf-8") as file_handle:
    file_handle.write(text)


def redact_path(path: Path, *, redact_paths: bool) -> str:
  """Render a path for persisted output, optionally redacting user details."""
  resolved_path = path.resolve()
  if not redact_paths:
    return str(resolved_path)

  try:
    return resolved_path.relative_to(REPO_ROOT).as_posix()
  except ValueError:
    return resolved_path.name


def load_existing_mock_log_bundle(
  bundle_dir: Path,
) -> tuple[MockLogResult, Path, Path]:
  """Load an existing mock-log bundle for loop reuse.

  Args:
    bundle_dir: Bundle directory containing mock log artifacts.

  Returns:
    The parsed mock log result, bundle directory, and bootstrap KQL path.

  Raises:
    FileNotFoundError: If required bundle artifacts are missing.
    ValueError: If the raw JSON cannot be parsed as ``MockLogResult``.
  """
  resolved_bundle_dir = bundle_dir.resolve()
  raw_json_path = resolved_bundle_dir / "mock_logs.raw.json"
  bootstrap_kql_path = resolved_bundle_dir / "bootstrap.kql"

  if not resolved_bundle_dir.exists():
    raise FileNotFoundError(f"Mock-log bundle not found: {resolved_bundle_dir}")
  if not raw_json_path.exists():
    raise FileNotFoundError(f"Mock-log JSON not found: {raw_json_path}")
  if not bootstrap_kql_path.exists():
    raise FileNotFoundError(f"Bootstrap KQL not found: {bootstrap_kql_path}")

  payload = json.loads(raw_json_path.read_text(encoding="utf-8"))
  mock_result = MockLogResult.model_validate(payload)
  return mock_result, resolved_bundle_dir, bootstrap_kql_path


def format_token_usage(token_usage: dict[str, int] | None) -> str:
  """Render token usage in a compact human-readable format.

  Args:
    token_usage: Token usage dictionary with ``input``, ``output``, and
      ``total`` keys, or ``None`` when unavailable.

  Returns:
    A compact human-readable token summary.
  """
  if token_usage is None:
    return "unknown"

  return (
    f"{token_usage.get('input', 0)} input + "
    f"{token_usage.get('output', 0)} output = "
    f"{token_usage.get('total', 0)} total"
  )


def accumulate_token_usage(
  total: dict[str, int],
  token_usage: dict[str, int] | None,
) -> None:
  """Accumulate token usage into the provided total dictionary.

  Args:
    total: Running token usage totals to mutate in place.
    token_usage: Per-step token usage to add into ``total``.
  """
  if token_usage is None:
    return

  total["input"] += token_usage.get("input", 0)
  total["output"] += token_usage.get("output", 0)
  total["total"] += token_usage.get("total", 0)


async def run_table_selection_agent(
  prompt_text: str,
  *,
  model_provider: str,
  model_name: str,
  verbose: bool = False,
) -> TableSelectionResult:
  """Use MCP tools to select the most relevant tables for the prompt.

  Args:
    prompt_text: Original detection request text.
    model_provider: Model provider used for the agent.
    model_name: Model name used for the agent.
    verbose: Whether to emit verbose agent events to stderr.

  Returns:
    Structured table selection output with token usage attached.
  """
  model = create_chat_model(provider=model_provider, model_name=model_name)
  client = MultiServerMCPClient(MCP_SERVER_CONFIG)
  tools = await client.get_tools()
  agent = create_agent(model, tools, response_format=TableSelectionResult)

  messages = [
    SystemMessage(content=TABLE_SELECTION_SYSTEM_PROMPT),
    HumanMessage(content=prompt_text),
  ]

  result = cast(AgentResponse, await agent.ainvoke({"messages": messages}))

  if verbose:
    print_agent_events(result["messages"], stream=sys.stderr)

  total_input_tokens, total_output_tokens = collect_token_usage(result["messages"])
  total_tokens = total_input_tokens + total_output_tokens
  APP_LOGGER.info(
    (
      f"[Tokens: {total_input_tokens} input + {total_output_tokens} output = "
      f"{total_tokens} total]"
    ),
    stderr=True,
  )
  structured_response = cast(TableSelectionResult, result["structured_response"])
  structured_response.token_usage = {
    "input": total_input_tokens,
    "output": total_output_tokens,
    "total": total_tokens,
  }
  return structured_response


def summarize_mock_logs(mock_result: MockLogResult) -> dict[str, Any]:
  """Return a compact summary of generated mock logs for evaluation.

  Args:
    mock_result: Structured mock log generation result.

  Returns:
    A JSON-serializable summary containing table counts, columns, and sample
    rows for evaluator input.
  """
  tables: list[dict[str, Any]] = []

  for table in mock_result.mock_logs:
    sample_rows = table.rows[:3]
    columns = list(sample_rows[0]) if sample_rows else []
    tables.append(
      {
        "table_name": table.table_name,
        "purpose": table.purpose,
        "row_count": len(table.rows),
        "sample_columns": columns,
        "sample_rows": sample_rows,
      }
    )

  return {
    "request": mock_result.request,
    "ioc_summary": mock_result.ioc_summary,
    "tables_used": mock_result.tables_used,
    "tables": tables,
  }


def summarize_execution_result(
  candidate: QueryCandidateExecution,
) -> dict[str, Any]:
  """Return a compact summary of one query execution.

  Args:
    candidate: Executed query candidate result.

  Returns:
    A JSON-serializable summary of the execution outcome.
  """
  if not candidate.success or candidate.execution_result is None:
    return {
      "candidate_index": candidate.candidate_index,
      "success": False,
      "error": candidate.error,
      "query": candidate.query,
    }

  tables: list[dict[str, Any]] = []
  for table in candidate.execution_result.tables:
    tables.append(
      {
        "row_count": table.row_count,
        "columns": list(table.columns),
        "sample_rows": table.rows[:3],
      }
    )

  return {
    "candidate_index": candidate.candidate_index,
    "success": True,
    "total_rows": candidate.total_rows,
    "query": candidate.query,
    "tables": tables,
  }


def parse_iso_datetime(value: Any) -> datetime | None:
  """Parse an ISO-8601 datetime string into a timezone-aware datetime.

  Args:
    value: Candidate value to parse.

  Returns:
    A UTC-aware ``datetime`` when parsing succeeds, otherwise ``None``.
  """
  if not isinstance(value, str):
    return None

  normalized = value.replace("Z", "+00:00")
  try:
    parsed = datetime.fromisoformat(normalized)
  except ValueError:
    return None

  if parsed.tzinfo is None:
    return parsed.replace(tzinfo=UTC)

  return parsed.astimezone(UTC)


def infer_query_now(mock_result: MockLogResult) -> str | None:
  """Infer a ``query_now`` timestamp from generated mock log datetime values.

  Args:
    mock_result: Structured mock log generation result.

  Returns:
    An ISO-8601 UTC timestamp one minute after the latest generated timestamp,
    or ``None`` if no datetime values are found.
  """
  latest_timestamp: datetime | None = None

  for table in mock_result.mock_logs:
    for row in table.rows:
      for value in row.values():
        parsed = parse_iso_datetime(value)
        if parsed is None:
          continue
        if latest_timestamp is None or parsed > latest_timestamp:
          latest_timestamp = parsed

  if latest_timestamp is None:
    return None

  return (
    (latest_timestamp + timedelta(minutes=1))
    .isoformat()
    .replace(
      "+00:00",
      "Z",
    )
  )


def compose_bootstrapped_query(bootstrap_kql: str, query: str) -> str:
  """Prefix a generated query with the bootstrap externaldata definitions.

  Args:
    bootstrap_kql: Bootstrap ``externaldata(...)`` statements.
    query: Generated query candidate.

  Returns:
    A single executable KQL string with bootstrap definitions prepended.
  """
  return f"{bootstrap_kql.rstrip()}\n\n{query.strip()}"


def execute_query_candidates(
  queries: list[str],
  *,
  bootstrap_kql: str,
  query_now: str | None,
) -> list[QueryCandidateExecution]:
  """Execute each generated query against the generated mock log bundle.

  Args:
    queries: Candidate queries to execute.
    bootstrap_kql: Bootstrap ``externaldata(...)`` statements.
    query_now: Optional Kusto ``query_now`` override.

  Returns:
    Execution records for all query candidates.
  """
  executions: list[QueryCandidateExecution] = []

  for index, query in enumerate(queries, start=1):
    full_query = compose_bootstrapped_query(bootstrap_kql, query)
    try:
      execution_result = execute_query(full_query, query_now=query_now)
      total_rows = sum(table.row_count for table in execution_result.tables)
      executions.append(
        QueryCandidateExecution(
          candidate_index=index,
          query=query,
          success=True,
          total_rows=total_rows,
          execution_result=execution_result,
        )
      )
    except Exception as exc:
      executions.append(
        QueryCandidateExecution(
          candidate_index=index,
          query=query,
          success=False,
          total_rows=0,
          error=str(exc),
        )
      )

  return executions


def print_candidate_execution_summaries(
  candidate_executions: list[QueryCandidateExecution],
  *,
  log_path: Path | None = None,
) -> None:
  """Print each candidate query and a compact execution summary to stderr.

  Args:
    candidate_executions: Query candidate execution results to print.
    log_path: Optional path to the loop log file.
  """
  for candidate in candidate_executions:
    write_log_block(
      f"  Candidate {candidate.candidate_index} query:\n{candidate.query}",
      log_path=log_path,
    )

    if not candidate.success or candidate.execution_result is None:
      log_line(
        f"  Candidate {candidate.candidate_index} failed: {candidate.error}",
        log_path=log_path,
      )
      continue

    log_line(
      f"  Candidate {candidate.candidate_index} execution:",
      log_path=log_path,
    )
    buffer = io.StringIO()
    with redirect_stderr(buffer):
      print_query_execution_summary(candidate.execution_result)
    write_log_block(buffer.getvalue(), log_path=log_path)


def print_iteration_evaluation(
  iteration: int,
  evaluation: IterationEvaluationResult,
  *,
  log_path: Path | None = None,
) -> None:
  """Print the evaluator decision for a loop iteration to stderr.

  Args:
    iteration: One-based iteration index.
    evaluation: Evaluation result to print.
    log_path: Optional path to the loop log file.
  """
  log_line(
    (
      f"Iteration {iteration} evaluation: "
      f"criteria_met={evaluation.criteria_met}, "
      f"best_query_index={evaluation.best_query_index}"
    ),
    log_path=log_path,
  )
  log_line(f"  Feedback: {evaluation.feedback}", log_path=log_path)
  if not evaluation.criteria_met:
    log_line(
      f"  Refined request: {evaluation.refined_request}",
      log_path=log_path,
    )


async def run_iteration_evaluator(
  *,
  original_prompt: str,
  current_request: str,
  mock_result: MockLogResult,
  query_result: KQLQueryResult,
  candidate_executions: list[QueryCandidateExecution],
  prior_feedback: list[str],
  model_provider: str,
  model_name: str,
  verbose: bool = False,
) -> IterationEvaluationResult:
  """Evaluate query candidates and produce the next refinement instruction.

  Args:
    original_prompt: Original user request for the loop.
    current_request: Current refined request being evaluated.
    mock_result: Structured mock log generation result.
    query_result: Structured KQL generation result.
    candidate_executions: Execution results for generated query candidates.
    prior_feedback: Prior evaluator feedback from earlier iterations.
    model_provider: Model provider used for the evaluator.
    model_name: Model name used for the evaluator.
    verbose: Whether to emit verbose agent events to stderr.

  Returns:
    Structured evaluator output with token usage attached.
  """
  model = create_chat_model(provider=model_provider, model_name=model_name)
  agent = create_agent(model, [], response_format=IterationEvaluationResult)

  payload = {
    "original_prompt": original_prompt,
    "current_request": current_request,
    "generated_query_request": query_result.request,
    "generated_queries": query_result.queries,
    "query_explanation": query_result.explanation,
    "tables_used": query_result.tables_used,
    "mock_log_summary": summarize_mock_logs(mock_result),
    "candidate_executions": [
      summarize_execution_result(candidate) for candidate in candidate_executions
    ],
    "prior_feedback": prior_feedback,
  }

  messages = [
    SystemMessage(content=EVALUATION_SYSTEM_PROMPT),
    HumanMessage(content=json.dumps(payload, indent=2)),
  ]

  result = cast(AgentResponse, await agent.ainvoke({"messages": messages}))

  if verbose:
    print_agent_events(result["messages"], stream=sys.stderr)

  total_input_tokens, total_output_tokens = collect_token_usage(result["messages"])
  total_tokens = total_input_tokens + total_output_tokens
  APP_LOGGER.info(
    (
      f"[Tokens: {total_input_tokens} input + {total_output_tokens} output = "
      f"{total_tokens} total]"
    ),
    stderr=True,
  )
  structured_response = cast(
    IterationEvaluationResult,
    result["structured_response"],
  )
  structured_response.token_usage = {
    "input": total_input_tokens,
    "output": total_output_tokens,
    "total": total_tokens,
  }
  return structured_response


def load_prompt_file(prompt_file: Path) -> str:
  """Load a non-empty prompt file.

  Args:
    prompt_file: Prompt file to read.

  Returns:
    Trimmed prompt text.

  Raises:
    FileNotFoundError: If the prompt file does not exist.
    ValueError: If the prompt file is empty after trimming whitespace.
  """
  if not prompt_file.exists():
    raise FileNotFoundError(f"Prompt file not found: {prompt_file}")

  prompt_text = prompt_file.read_text(encoding="utf-8").strip()
  if not prompt_text:
    raise ValueError(f"Prompt file is empty: {prompt_file}")

  return prompt_text


async def async_main(args: Args) -> None:
  """Run the end-to-end detection loop.

  Args:
    args: Parsed command-line arguments.
  """
  if args.rows_per_table < 1:
    APP_LOGGER.error("--rows-per-table must be at least 1.")
    sys.exit(2)

  if args.max_iterations < 1:
    APP_LOGGER.error("--max-iterations must be at least 1.")
    sys.exit(2)

  try:
    prompt_text = load_prompt_file(args.prompt_file)
  except Exception as exc:
    APP_LOGGER.error(f"Error: {exc}")
    sys.exit(2)

  table_selection: TableSelectionResult | None = None
  mock_result: MockLogResult
  if args.reuse_mock_log_bundle is not None:
    log_line(f"Reusing mock-log bundle: {args.reuse_mock_log_bundle}")
    try:
      mock_result, bundle_dir, bootstrap_kql_path = load_existing_mock_log_bundle(
        args.reuse_mock_log_bundle
      )
    except Exception as exc:
      APP_LOGGER.error(f"Error: {exc}")
      sys.exit(2)
    selected_tables = mock_result.tables_used
  else:
    log_line("Selecting relevant tables...")
    table_selection = await run_table_selection_agent(
      prompt_text,
      model_provider=args.model_provider,
      model_name=args.model,
      verbose=args.verbose,
    )
    log_line(f"Selected tables: {', '.join(table_selection.tables)}")

    log_line("Generating mock logs...")
    mock_request = build_mock_log_request(
      tables=table_selection.tables,
      ioc_text=prompt_text,
      rows_per_table=args.rows_per_table,
      tables_are_user_selected=True,
    )
    mock_result = await run_mock_log_agent(
      mock_request,
      model_provider=args.model_provider,
      model_name=args.model,
      verbose=args.verbose,
    )

    output_name = args.output_name or args.prompt_file.stem
    bundle_dir = write_output_bundle(
      mock_result,
      bootstrap_base_url=args.bootstrap_base_url,
      output_name=output_name,
      write_bootstrap_kql=True,
    )
    bootstrap_kql_path = bundle_dir / "bootstrap.kql"
    selected_tables = table_selection.tables

  log_path = bundle_dir / "loop.log"
  log_path.write_text("", encoding="utf-8")
  write_log_block(
    "\n".join(
      [
        f"Prompt file: {args.prompt_file}",
        f"Bundle dir: {bundle_dir}",
        f"Bootstrap KQL: {bootstrap_kql_path}",
        f"Selected tables: {', '.join(selected_tables)}",
      ]
    ),
    log_path=log_path,
  )
  bootstrap_kql = bootstrap_kql_path.read_text(encoding="utf-8")
  query_now = infer_query_now(mock_result)
  if query_now is not None:
    log_line(f"Using query_now: {query_now}", log_path=log_path)

  prior_feedback: list[str] = []
  current_request = prompt_text
  iterations: list[LoopIterationRecord] = []
  criteria_met = False
  final_iteration: int | None = None
  final_query: str | None = None
  final_query_index: int | None = None
  total_token_usage = {"input": 0, "output": 0, "total": 0}

  if table_selection is not None:
    accumulate_token_usage(total_token_usage, table_selection.token_usage)
    log_line(
      f"Table selection tokens: {format_token_usage(table_selection.token_usage)}",
      log_path=log_path,
    )
  else:
    log_line(
      "Table selection tokens: skipped while reusing mock-log bundle",
      log_path=log_path,
    )

  if args.reuse_mock_log_bundle is None:
    accumulate_token_usage(total_token_usage, mock_result.token_usage)
    log_line(
      f"Mock log generation tokens: {format_token_usage(mock_result.token_usage)}",
      log_path=log_path,
    )
  else:
    log_line(
      "Mock log generation tokens: skipped while reusing mock-log bundle",
      log_path=log_path,
    )

  for iteration in range(1, args.max_iterations + 1):
    log_line(
      f"Iteration {iteration}: generating KQL query...",
      log_path=log_path,
    )
    kql_result = await run_kql_agent(
      current_request,
      model_provider=args.model_provider,
      model_name=args.model,
      verbose=args.verbose,
    )
    accumulate_token_usage(total_token_usage, kql_result.token_usage)
    log_line(
      (
        f"Iteration {iteration}: KQL generation tokens: "
        f"{format_token_usage(kql_result.token_usage)}"
      ),
      log_path=log_path,
    )

    log_line(
      f"Iteration {iteration}: executing query candidate(s)...",
      log_path=log_path,
    )
    candidate_executions = execute_query_candidates(
      kql_result.queries,
      bootstrap_kql=bootstrap_kql,
      query_now=query_now,
    )
    print_candidate_execution_summaries(candidate_executions, log_path=log_path)

    log_line(
      f"Iteration {iteration}: evaluating results...",
      log_path=log_path,
    )
    evaluation = await run_iteration_evaluator(
      original_prompt=prompt_text,
      current_request=current_request,
      mock_result=mock_result,
      query_result=kql_result,
      candidate_executions=candidate_executions,
      prior_feedback=prior_feedback,
      model_provider=args.model_provider,
      model_name=args.model,
      verbose=args.verbose,
    )
    accumulate_token_usage(total_token_usage, evaluation.token_usage)
    log_line(
      (
        f"Iteration {iteration}: evaluation tokens: "
        f"{format_token_usage(evaluation.token_usage)}"
      ),
      log_path=log_path,
    )
    print_iteration_evaluation(iteration, evaluation, log_path=log_path)

    iterations.append(
      LoopIterationRecord(
        iteration=iteration,
        request=current_request,
        generated_queries=kql_result.queries,
        kql_generation_token_usage=kql_result.token_usage,
        candidate_executions=candidate_executions,
        evaluation=evaluation,
      )
    )

    prior_feedback.append(evaluation.feedback)

    if evaluation.criteria_met:
      criteria_met = True
      final_iteration = iteration
      final_query_index = evaluation.best_query_index
      if final_query_index is not None and 1 <= final_query_index <= len(
        kql_result.queries
      ):
        final_query = kql_result.queries[final_query_index - 1]
      elif kql_result.queries:
        final_query = kql_result.queries[0]
        final_query_index = 1
      break

    current_request = evaluation.refined_request

  result = DetectionAgentLoopResult(
    prompt_file=redact_path(args.prompt_file, redact_paths=args.redact_paths),
    bundle_dir=redact_path(bundle_dir, redact_paths=args.redact_paths),
    bootstrap_kql_path=redact_path(
      bootstrap_kql_path,
      redact_paths=args.redact_paths,
    ),
    log_path=redact_path(log_path, redact_paths=args.redact_paths),
    result_path="",
    tables_selected=selected_tables,
    criteria_met=criteria_met,
    table_selection_token_usage=(
      table_selection.token_usage if table_selection is not None else None
    ),
    mock_log_token_usage=(
      None if args.reuse_mock_log_bundle is not None else mock_result.token_usage
    ),
    total_token_usage=total_token_usage,
    query_now=query_now,
    final_iteration=final_iteration,
    final_query=final_query,
    final_query_index=final_query_index,
    iterations=iterations,
  )
  result_path = bundle_dir / "loop_result.json"
  result.result_path = redact_path(result_path, redact_paths=args.redact_paths)
  result_path.write_text(result.model_dump_json(indent=2), encoding="utf-8")

  log_line("Loop complete.", log_path=log_path)
  log_line(f"Result JSON: {result_path}", log_path=log_path)
  log_line(f"Loop log: {log_path}", log_path=log_path)
  log_line(f"Criteria met: {criteria_met}", log_path=log_path)
  log_line(
    f"Final token usage: {format_token_usage(total_token_usage)}",
    log_path=log_path,
  )
  if final_iteration is not None:
    log_line(f"Final iteration: {final_iteration}", log_path=log_path)
  if final_query_index is not None:
    log_line(f"Final query index: {final_query_index}", log_path=log_path)


def main() -> None:
  """Parse arguments and run the loop."""
  parser = argparse.ArgumentParser(
    description=(
      "Run a prompt-driven loop that generates mock logs, generates KQL, "
      "executes the query, and refines until the criteria are met"
    )
  )
  add_log_mode_argument(parser)
  parser.add_argument(
    "prompt_file",
    type=Path,
    help="Prompt file to use as the end-to-end detection request",
  )
  parser.add_argument(
    "--rows-per-table",
    type=int,
    default=3,
    help="Target number of generated mock rows per selected table (default: 3)",
  )
  parser.add_argument(
    "--max-loop",
    dest="max_iterations",
    type=int,
    help=(
      "Alias for --max-iterations. Maximum number of query-refinement "
      "iterations to run."
    ),
  )
  parser.add_argument(
    "--max-iterations",
    type=int,
    default=3,
    help="Maximum number of query-refinement iterations to run (default: 3)",
  )
  parser.add_argument(
    "--bootstrap-base-url",
    default="https://caddy",
    help=(
      "Base URL used by the generated bootstrap.kql for the mock-log bundle "
      "(default: https://caddy)"
    ),
  )
  parser.add_argument(
    "--output-name",
    help="Optional name for the generated mock-log bundle under samples/",
  )
  parser.add_argument(
    "--reuse-mock-log-bundle",
    type=Path,
    help=(
      "Reuse an existing mock-log bundle directory containing "
      "mock_logs.raw.json and bootstrap.kql. When provided, the loop skips "
      "table selection and mock log generation."
    ),
  )
  parser.add_argument(
    "--redact-paths",
    action="store_true",
    help=(
      "Store repo-relative paths in loop_result.json instead of absolute "
      "filesystem paths to avoid exposing user-specific directory names."
    ),
  )
  parser.add_argument(
    "--model-provider",
    default=DEFAULT_MODEL_PROVIDER,
    help=(
      f"Model provider to use for all loop stages (default: {DEFAULT_MODEL_PROVIDER})"
    ),
  )
  parser.add_argument(
    "--model",
    default=DEFAULT_ANTHROPIC_MODEL_NAME,
    help="Model name to use for all loop stages (defaults to per provider default)",
  )
  parser.add_argument(
    "-v",
    "--verbose",
    action="store_true",
    help="Print verbose agent messages to stderr for each loop stage",
  )
  args = parser.parse_args(namespace=Args())
  APP_LOGGER.set_mode(args.log_mode)
  asyncio.run(async_main(args))


if __name__ == "__main__":
  main()
