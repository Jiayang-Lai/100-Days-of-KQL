"""Generate a day report markdown file in the repository's established style."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any, cast

from app_logger import LogMode, add_log_mode_argument, build_app_logger
from dotenv import load_dotenv
from langchain_core.messages import HumanMessage, SystemMessage
from model_factory import (
  DEFAULT_MODEL_PROVIDER,
  create_chat_model,
)
from pydantic import BaseModel, Field, ValidationError

load_dotenv()

APP_LOGGER = build_app_logger("write_day_report")
TEMPLATE_PATH = Path(__file__).parent.parent / "templates" / "day.md"
DAYS_DIR = Path(__file__).parent.parent / "days"
PROMPT_GENERATION_SYSTEM_PROMPT = """You generate `day-X.prompt.md` files for a KQL detection workflow.

Return a single plain-text prompt that will be passed to another agent which
generates KQL.

The prompt you produce must:
- be directly usable as the full contents of `day-X.prompt.md`
- clearly ask for a KQL query or KQL detection logic
- preserve the important IOC material from the source document, including
  domains, IPs, URLs, paths, hashes, filenames, process indicators, and
  other detection-relevant artifacts
- tell the downstream agent to restore defanged indicators to their original
  form in the final query when needed
- prefer a compact markdown table for IOC material when it improves clarity
- prefer a single complete KQL query unless the source strongly suggests
  otherwise

Do not include commentary about your reasoning.
Do not wrap the output in code fences.
Return only the prompt text.
"""  # noqa: E501
NOTE_GENERATION_SYSTEM_PROMPT = """You write the `# Note` section for a daily KQL learning journal.

Return concise markdown that:
- reads like a human-written project note, not an incident dump
- summarizes the case or topic from the source document
- highlights the detection-relevant details and why the case matters
- avoids copy-pasting long IOC lists unless a very small number of indicators
  are central to the story
- fits naturally under a `# Note` heading

Do not include a heading.
Do not use code fences.
Return only the markdown for the note body.
"""  # noqa: E501


class TokenUsage(BaseModel):
  """Token usage summary."""

  input: int | None = None
  output: int | None = None
  total: int | None = None
  input_tokens: int | None = None
  output_tokens: int | None = None
  total_tokens: int | None = None

  def normalized(self) -> tuple[int, int, int] | None:
    """Return normalized token usage values when available."""
    input_value = self.input if self.input is not None else self.input_tokens
    output_value = self.output if self.output is not None else self.output_tokens
    total_value = self.total if self.total is not None else self.total_tokens

    if input_value is None or output_value is None or total_value is None:
      return None

    return input_value, output_value, total_value


class IterationEvaluationResult(BaseModel):
  """Evaluation outcome for a loop iteration."""

  criteria_met: bool
  best_query_index: int | None = None
  feedback: str
  refined_request: str
  token_usage: TokenUsage | None = None


class LoopIterationRecord(BaseModel):
  """Persisted details for one loop iteration."""

  iteration: int
  request: str
  generated_queries: list[str]
  kql_generation_token_usage: TokenUsage | None = None
  candidate_executions: list[QueryCandidateExecution] = Field(default_factory=list)
  evaluation: IterationEvaluationResult


class DetectionAgentLoopResult(BaseModel):
  """Structured result of the end-to-end loop."""

  criteria_met: bool
  final_iteration: int | None = None
  final_query: str | None = None
  final_query_index: int | None = None
  total_token_usage: TokenUsage | None = None
  iterations: list[LoopIterationRecord] = Field(default_factory=list)


class QueryCandidateExecution(BaseModel):
  """Execution result for one generated KQL candidate."""

  candidate_index: int
  query: str
  success: bool
  total_rows: int
  error: str | None = None


class KQLQueryResult(BaseModel):
  """Structured output for KQL query generation."""

  request: str
  queries: list[str]
  explanation: str
  tables_used: list[str]
  token_usage: TokenUsage | None = None


class DayReportArgs(argparse.Namespace):
  """Command-line arguments for prompt and report generation.

  The script supports two adjacent workflows:

  1. Prompt generation:
     - ``source_document`` provides the initial topic/IOC write-up.
     - ``prompt_output`` chooses where the generated ``day-X.prompt.md`` file
       is written.
     - ``prompt_prefix`` overrides the default instruction wrapper used for the
       generated prompt.

  2. Report generation:
     - ``output`` chooses the ``day-X.md`` report destination.
     - ``note``, ``intro``, ``summary``, ``official_doc_label``,
       ``official_doc_url``, ``link``, ``prompt_file``, ``prompt_text``, and
       ``result_json`` affect the rendered markdown report.

  Important interaction:
  - If ``source_document`` is provided, the script will generate a prompt file.
  - ``note`` does not change prompt generation. It fills the ``# Note``
    section of the day report, and if omitted the script can generate that
    section automatically from ``source_document`` with the configured model
    when writing a report.
  - If you provide only prompt-generation inputs, the script runs in
    prompt-only mode and does not create a day report.
  - If you provide report-related inputs as well, the script can generate both
    the prompt file and the report in one run.
  """

  day_number: int
  embed_prompt: bool
  intro: str | None
  link: list[str]
  log_mode: LogMode
  model: str
  model_provider: str
  note: str | None
  official_doc_label: str | None
  official_doc_url: str | None
  output: Path | None
  prompt_file: Path | None
  prompt_output: Path | None
  prompt_prefix: str | None
  prompt_text: str | None
  result_json: Path | None
  source_document: Path | None
  summary: str | None
  title: str | None


class ParsedResult(BaseModel):
  """Normalized report content extracted from a result JSON file."""

  loop_result: DetectionAgentLoopResult | None = None
  kql_result: KQLQueryResult | None = None
  queries: list[str]
  token_usage: TokenUsage | None = None
  summary_text: str | None = None


class PromptGenerationResult(BaseModel):
  """Structured prompt generation output."""

  prompt_text: str


class NoteGenerationResult(BaseModel):
  """Structured note generation output."""

  note_markdown: str


def format_token_usage(token_usage: dict[str, int] | None) -> str:
  """Render token usage in a compact human-readable format."""
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
  """Accumulate token usage into the provided total dictionary."""
  if token_usage is None:
    return

  total["input"] += token_usage.get("input", 0)
  total["output"] += token_usage.get("output", 0)
  total["total"] += token_usage.get("total", 0)


def extract_token_usage(raw_message: Any) -> dict[str, int] | None:
  """Extract normalized token usage from a raw model response message."""
  usage_metadata = getattr(raw_message, "usage_metadata", None)
  if not usage_metadata:
    return None

  input_tokens = usage_metadata.get("input_tokens", 0)
  output_tokens = usage_metadata.get("output_tokens", 0)
  return {
    "input": input_tokens,
    "output": output_tokens,
    "total": input_tokens + output_tokens,
  }


def parse_args() -> DayReportArgs:
  """Parse command-line arguments."""
  parser = argparse.ArgumentParser(
    description="Write a day report markdown file following the project style"
  )
  add_log_mode_argument(parser)
  parser.add_argument("--day-number", type=int, required=True, help="Day number")
  parser.add_argument(
    "--model-provider",
    default=DEFAULT_MODEL_PROVIDER,
    help=(
      "Model provider to use for LLM-based prompt generation "
      f"(default: {DEFAULT_MODEL_PROVIDER})"
    ),
  )
  parser.add_argument(
    "--model",
    help=(
      "Model name to use for LLM-based prompt generation (defaults to "
      "default values per provider)"
    ),
  )
  parser.add_argument(
    "--title",
    help=(
      "Short topic label used in the generated intro paragraph and, when "
      "--source-document is used, in the generated prompt instructions."
    ),
  )
  parser.add_argument(
    "--intro",
    help=(
      "Custom intro paragraph placed below the day heading in the report. "
      "This affects only the markdown report, not prompt generation."
    ),
  )
  parser.add_argument(
    "--note",
    help=(
      "Free-form content for the report's '# Note' section. This is report-only "
      "content; it does not modify the generated prompt even when "
      "--source-document is also provided. If omitted while generating a "
      "report from --source-document, the note is generated automatically "
      "from the source document with the configured model."
    ),
  )
  parser.add_argument(
    "--summary",
    help=(
      "Short paragraph placed under 'Attempt 1' before the prompt section in "
      "the report. If omitted and --result-json is provided, the script derives "
      "a summary from the result JSON."
    ),
  )
  parser.add_argument(
    "--official-doc-label",
    help="Official document link label for the report's '# Official Document' section.",
  )
  parser.add_argument(
    "--official-doc-url",
    help="Official document link URL for the report's '# Official Document' section.",
  )
  parser.add_argument(
    "--prompt-file",
    type=Path,
    help=(
      "Existing prompt file to reference or embed in the report. If "
      "--source-document is also provided and --prompt-file is omitted, the "
      "newly generated prompt file will be used automatically."
    ),
  )
  parser.add_argument(
    "--source-document",
    type=Path,
    help=(
      "Source document that explains the topic and lists the IOCs. "
      "When provided, the script will generate a day-X.prompt.md file from it. "
      "This input is used only for prompt generation unless you also provide "
      "report-related arguments. When a report is written and --note is "
      "omitted, this document is also used to generate the '# Note' section."
    ),
  )
  parser.add_argument(
    "--prompt-output",
    type=Path,
    help=(
      "Output path for the generated prompt file. Defaults to days/day-<n>.prompt.md."
    ),
  )
  parser.add_argument(
    "--prompt-prefix",
    help=(
      "Optional instruction prefix to place before the source document in the "
      "generated prompt file. Use this when the default 'generate a KQL query' "
      "framing is too generic for a specific day."
    ),
  )
  parser.add_argument(
    "--prompt-text",
    help=(
      "Inline prompt text to embed directly in the report. This affects only "
      "report rendering and does not write a prompt file."
    ),
  )
  parser.add_argument(
    "--embed-prompt",
    action="store_true",
    help=(
      "Embed prompt contents in the report instead of only linking to the prompt file."
    ),
  )
  parser.add_argument(
    "--result-json",
    type=Path,
    help=(
      "KQL result JSON or loop result JSON to summarize in the report. This "
      "is report-only input and is ignored for prompt generation."
    ),
  )
  parser.add_argument(
    "--link",
    action="append",
    default=[],
    help=(
      "Additional report link. Use either a bare URL or 'Label|URL'. Repeat "
      "for multiple links."
    ),
  )
  parser.add_argument(
    "--output",
    type=Path,
    help=(
      "Output path for the generated day report markdown. Defaults to "
      "days/day-<n>.md. If you omit report-related inputs, the script can run "
      "in prompt-only mode and no report file will be written."
    ),
  )
  return cast(DayReportArgs, parser.parse_args(namespace=DayReportArgs()))


def load_text_file(path: Path) -> str:
  """Load a text file and return trimmed contents."""
  if not path.exists():
    raise FileNotFoundError(f"File not found: {path}")

  text = path.read_text(encoding="utf-8").strip()
  if not text:
    raise ValueError(f"File is empty: {path}")

  return text


def parse_result_json(path: Path) -> ParsedResult:
  """Parse a report source JSON file.

  Args:
    path: JSON file path.

  Returns:
    Normalized result content.
  """
  raw_text = load_text_file(path)
  payload = json.loads(raw_text)

  try:
    loop_result = DetectionAgentLoopResult.model_validate(payload)
  except ValidationError:
    loop_result = None

  if loop_result is not None and loop_result.iterations:
    queries = []
    if loop_result.final_query:
      queries = [loop_result.final_query]
    elif loop_result.iterations:
      queries = loop_result.iterations[-1].generated_queries

    summary_lines = [
      (
        f"The loop completed with `criteria_met={loop_result.criteria_met}` "
        f"after {len(loop_result.iterations)} iteration(s)."
      )
    ]
    if loop_result.final_iteration is not None:
      summary_lines.append(f"Final iteration: {loop_result.final_iteration}.")
    if loop_result.final_query_index is not None:
      summary_lines.append(
        f"Selected query candidate index: {loop_result.final_query_index}."
      )
    if loop_result.iterations:
      summary_lines.append(loop_result.iterations[-1].evaluation.feedback)

    return ParsedResult(
      loop_result=loop_result,
      queries=queries,
      token_usage=loop_result.total_token_usage,
      summary_text="\n\n".join(summary_lines),
    )

  kql_result = KQLQueryResult.model_validate(payload)
  return ParsedResult(
    kql_result=kql_result,
    queries=kql_result.queries,
    token_usage=kql_result.token_usage,
    summary_text=kql_result.explanation,
  )


def build_intro(day_number: int, title: str | None, intro: str | None) -> str:
  """Build the opening paragraph."""
  if intro:
    return intro.strip()
  if title:
    return f"Today's query is for {title.strip().rstrip('.')}."
  return f"Today's work focuses on day {day_number}."


def build_generated_note(
  *,
  title: str | None,
  source_document_text: str,
  model_provider: str,
  model_name: str,
) -> tuple[str, dict[str, int] | None]:
  """Generate the report note section from a source document with an LLM.

  Args:
    title: Optional short title for the topic.
    source_document_text: Raw source markdown text.
    model_provider: Model provider name.
    model_name: Model identifier within the provider.

  Returns:
    Markdown for the report's note section plus token usage when available.
  """
  model = create_chat_model(provider=model_provider, model_name=model_name)
  structured_model = model.with_structured_output(
    NoteGenerationResult,
    include_raw=True,
  )

  request_parts = [
    "Write the `# Note` section for the daily report from the source document below.",
  ]
  if title:
    request_parts.append(f"Topic title: {title.strip()}")
  request_parts.extend(
    [
      "",
      "Source document:",
      source_document_text.strip(),
    ]
  )

  messages: list[Any] = [
    SystemMessage(content=NOTE_GENERATION_SYSTEM_PROMPT),
    HumanMessage(content="\n".join(request_parts)),
  ]
  response = cast(dict[str, Any], structured_model.invoke(messages))
  result = cast(NoteGenerationResult | None, response.get("parsed"))
  if result is None:
    raise ValueError("Model did not return a parsed note result.")

  return result.note_markdown.strip(), extract_token_usage(response.get("raw"))


def build_generated_prompt(
  *,
  title: str | None,
  source_document_text: str,
  prompt_prefix: str | None,
  model_provider: str,
  model_name: str,
) -> tuple[str, dict[str, int] | None]:
  """Generate prompt text for the detection loop from a source document.

  Args:
    title: Optional short title for the topic.
    source_document_text: Source document describing the topic and IOCs.
    prompt_prefix: Optional custom prefix to override the default instructions.
    model_provider: Model provider name.
    model_name: Model identifier within the provider.

  Returns:
    Prompt text suitable for ``run_detection_agent_loop.py`` input plus token
    usage when available.
  """
  model = create_chat_model(provider=model_provider, model_name=model_name)
  structured_model = model.with_structured_output(
    PromptGenerationResult,
    include_raw=True,
  )

  request_parts = [
    "Create the full contents for `day-X.prompt.md` from the source document below.",
  ]
  if title:
    request_parts.append(f"Topic title: {title.strip()}")
  if prompt_prefix:
    request_parts.append(
      "Use the following instruction prefix as the starting framing of the prompt:"
    )
    request_parts.append(prompt_prefix.strip())
  request_parts.extend(
    [
      "",
      "Source document:",
      source_document_text.strip(),
    ]
  )

  messages: list[Any] = [
    SystemMessage(content=PROMPT_GENERATION_SYSTEM_PROMPT),
    HumanMessage(content="\n".join(request_parts)),
  ]
  response = cast(dict[str, Any], structured_model.invoke(messages))
  result = cast(PromptGenerationResult | None, response.get("parsed"))
  if result is None:
    raise ValueError("Model did not return a parsed prompt result.")

  return result.prompt_text.strip(), extract_token_usage(response.get("raw"))


def write_generated_prompt(
  *,
  day_number: int,
  title: str | None,
  source_document: Path,
  prompt_output: Path | None,
  prompt_prefix: str | None,
  model_provider: str,
  model_name: str,
) -> tuple[Path, dict[str, int] | None]:
  """Generate and write a prompt markdown file from a source document.

  Args:
    day_number: Day number used for the default output path.
    title: Optional short title for the topic.
    source_document: Source document describing the topic and IOCs.
    prompt_output: Optional explicit prompt output path.
    prompt_prefix: Optional custom prompt prefix.
    model_provider: Model provider name.
    model_name: Model identifier within the provider.

  Returns:
    The written prompt file path plus token usage when available.
  """
  prompt_path = prompt_output or DAYS_DIR / f"day-{day_number}.prompt.md"
  source_text = load_text_file(source_document)
  prompt_text, token_usage = build_generated_prompt(
    title=title,
    source_document_text=source_text,
    prompt_prefix=prompt_prefix,
    model_provider=model_provider,
    model_name=model_name,
  )
  prompt_path.write_text(prompt_text, encoding="utf-8")
  return prompt_path, token_usage


def render_official_doc(label: str | None, url: str | None) -> str:
  """Render the official document section content."""
  if label and url:
    return f"[{label}]({url})"
  return "[]()"


def render_prompt_section(
  *,
  output_path: Path,
  prompt_file: Path | None,
  prompt_text: str | None,
  embed_prompt: bool,
) -> str:
  """Render the prompt section body."""
  if prompt_text:
    return f"~~~markdown\n{prompt_text.strip()}\n~~~"

  if prompt_file is None:
    return ""

  if embed_prompt:
    return f"~~~markdown\n{load_text_file(prompt_file)}\n~~~"

  path_text = os.path.relpath(prompt_file, start=output_path.parent)
  path_text = Path(path_text).as_posix()

  return f"Please find the prompt from this [file]({path_text})."


def render_stats_table(token_usage: TokenUsage | None) -> str:
  """Render the stats table when token usage exists."""
  normalized = token_usage.normalized() if token_usage is not None else None
  if normalized is None:
    return ""

  input_tokens, output_tokens, total_tokens = normalized
  return "\n".join(
    [
      "Stats:",
      "",
      "| Token Type | Value |",
      "| ---------- | ----- |",
      f"| Input      | {input_tokens} |",
      f"| Output     | {output_tokens} |",
      f"| Total      | {total_tokens} |",
    ]
  )


def render_token_table(title: str, token_usage: TokenUsage | None) -> str:
  """Render a titled token usage table."""
  normalized = token_usage.normalized() if token_usage is not None else None
  if normalized is None:
    return ""

  input_tokens, output_tokens, total_tokens = normalized
  return "\n".join(
    [
      f"{title}:",
      "",
      "| Token Type | Value |",
      "| ---------- | ----- |",
      f"| Input      | {input_tokens} |",
      f"| Output     | {output_tokens} |",
      f"| Total      | {total_tokens} |",
    ]
  )


def render_queries(queries: list[str]) -> str:
  """Render one or more KQL queries."""
  if not queries:
    return ""

  intro = "Got the query:" if len(queries) == 1 else "These are the queries we got:"
  blocks = [intro, ""]
  for query in queries:
    blocks.append("```kql")
    blocks.append(query.rstrip())
    blocks.append("```")
    blocks.append("")

  return "\n".join(blocks).rstrip()


def shorten_text(value: str, *, max_length: int = 220) -> str:
  """Return a single-line shortened version of text."""
  compact = " ".join(value.split())
  if len(compact) <= max_length:
    return compact
  return compact[: max_length - 3].rstrip() + "..."


def render_attempt_overview(iteration: LoopIterationRecord) -> str:
  """Render a concise human-readable summary for one loop iteration."""
  candidate_count = len(iteration.generated_queries)
  execution_count = len(iteration.candidate_executions)
  successful_executions = [
    candidate for candidate in iteration.candidate_executions if candidate.success
  ]

  parts = [f"This attempt generated {candidate_count} query candidate(s)"]
  if execution_count:
    parts.append(f"and executed {execution_count} candidate(s)")
  sentence = " ".join(parts) + "."

  if iteration.evaluation.criteria_met:
    verdict = "The evaluator accepted this attempt."
  elif successful_executions:
    best_rows = max(candidate.total_rows for candidate in successful_executions)
    verdict = (
      "The query executed successfully, but the evaluator still requested "
      f"refinement after seeing up to {best_rows} matching row(s)."
    )
  else:
    verdict = "The attempt did not pass evaluation."

  feedback = shorten_text(iteration.evaluation.feedback)
  return " ".join([sentence, verdict, feedback])


def render_candidate_results(iteration: LoopIterationRecord) -> str:
  """Render execution outcomes for generated query candidates."""
  if not iteration.candidate_executions:
    return ""

  lines: list[str] = []
  for candidate in iteration.candidate_executions:
    if candidate.success:
      lines.append(
        f"- Candidate {candidate.candidate_index} executed successfully and returned {candidate.total_rows} row(s)."  # noqa: E501
      )
    else:
      error_text = shorten_text(candidate.error or "Execution failed.")
      lines.append(
        f"- Candidate {candidate.candidate_index} failed to execute: {error_text}"
      )
  return "\n".join(lines)


def render_iteration_stats(iteration: LoopIterationRecord) -> str:
  """Render token usage for one loop iteration."""
  kql_stats = render_token_table(
    "KQL generation stats",
    iteration.kql_generation_token_usage,
  )
  evaluation_stats = render_token_table(
    "Evaluation stats",
    iteration.evaluation.token_usage,
  )
  sections: list[str] = []

  if kql_stats:
    sections.append(kql_stats)
    sections.append("")

  if evaluation_stats:
    sections.append(evaluation_stats)

  return "\n".join(section for section in sections if section is not None).rstrip()


def render_loop_overview(loop_result: DetectionAgentLoopResult) -> str:
  """Render a short overview paragraph for a loop result."""
  attempt_count = len(loop_result.iterations)
  if attempt_count == 0:
    return ""

  base = (
    f"The workflow ran for {attempt_count} attempt(s) and finished with "
    f"`criteria_met={loop_result.criteria_met}`."
  )
  if loop_result.final_iteration is not None:
    base += f" The final accepted attempt was {loop_result.final_iteration}."
  elif loop_result.iterations:
    last_iteration = loop_result.iterations[-1]
    successful_rows = [
      candidate.total_rows
      for candidate in last_iteration.candidate_executions
      if candidate.success
    ]
    if successful_rows:
      base += (
        " The last attempt produced a runnable query that returned "
        f"{max(successful_rows)} row(s), but it still missed the evaluator's bar."
      )

  return base


def render_attempt_prompt(
  *,
  iteration: LoopIterationRecord,
  output_path: Path,
  prompt_file: Path | None,
  prompt_text: str | None,
  embed_prompt: bool,
) -> str:
  """Render the prompt block for one attempt."""
  if iteration.iteration == 1:
    return render_prompt_section(
      output_path=output_path,
      prompt_file=prompt_file,
      prompt_text=prompt_text,
      embed_prompt=embed_prompt,
    )

  return f"~~~markdown\n{iteration.request.strip()}\n~~~"


def render_loop_attempts(
  *,
  loop_result: DetectionAgentLoopResult,
  output_path: Path,
  prompt_file: Path | None,
  prompt_text: str | None,
  embed_prompt: bool,
) -> list[str]:
  """Render the Gen AI attempt sections for a loop result."""
  sections: list[str] = []

  overview = render_loop_overview(loop_result)
  if overview:
    sections.extend([overview, ""])

  for iteration in loop_result.iterations:
    sections.extend([f"## Attempt {iteration.iteration}", ""])
    sections.extend([render_attempt_overview(iteration), ""])
    sections.extend(["### Prompt", ""])
    prompt_block = render_attempt_prompt(
      iteration=iteration,
      output_path=output_path,
      prompt_file=prompt_file,
      prompt_text=prompt_text,
      embed_prompt=embed_prompt,
    )
    if prompt_block:
      sections.extend([prompt_block, ""])

    sections.extend(["### Result", ""])
    candidate_results = render_candidate_results(iteration)
    if candidate_results:
      sections.extend([candidate_results, ""])

    if iteration.evaluation.feedback:
      sections.extend(
        [
          "Evaluator feedback:",
          "",
          iteration.evaluation.feedback.strip(),
          "",
        ]
      )

    stats_text = render_iteration_stats(iteration)
    if stats_text:
      sections.extend([stats_text, ""])

    rendered_queries = render_queries(iteration.generated_queries)
    if rendered_queries:
      sections.extend([rendered_queries, ""])

  return sections


def parse_link_argument(value: str) -> tuple[str, str]:
  """Parse a `Label|URL` link argument."""
  stripped_value = value.strip()
  if "|" not in stripped_value:
    if not stripped_value:
      raise ValueError(
        f"Invalid --link value '{value}'. Expected a URL or 'Label|URL'."
      )
    return stripped_value, stripped_value

  label, url = stripped_value.split("|", 1)
  label = label.strip()
  url = url.strip()
  if not label or not url:
    raise ValueError(f"Invalid --link value '{value}'. Expected a URL or 'Label|URL'.")
  return label, url


def render_links(values: list[str]) -> str:
  """Render the links section."""
  if not values:
    return ""

  rendered: list[str] = []
  for value in values:
    label, url = parse_link_argument(value)
    rendered.append(f"- [{label}]({url})")
  return "\n".join(rendered)


def validate_report_inputs(args: DayReportArgs) -> None:
  """Validate report-only inputs before any token-consuming work starts."""
  has_official_doc_label = bool(
    args.official_doc_label and args.official_doc_label.strip()
  )
  has_official_doc_url = bool(args.official_doc_url and args.official_doc_url.strip())

  if has_official_doc_label != has_official_doc_url:
    raise ValueError(
      "Provide both --official-doc-label and --official-doc-url together."
    )

  for value in args.link:
    parse_link_argument(value)


def render_single_attempt(
  *,
  output_path: Path,
  prompt_file: Path | None,
  prompt_text: str | None,
  embed_prompt: bool,
  parsed_result: ParsedResult | None,
  summary_text: str | None,
) -> list[str]:
  """Render a single-attempt Gen AI section."""
  prompt_section = render_prompt_section(
    output_path=output_path,
    prompt_file=prompt_file,
    prompt_text=prompt_text,
    embed_prompt=embed_prompt,
  )
  sections: list[str] = ["## Attempt 1", ""]

  if summary_text:
    sections.extend([summary_text.strip(), ""])

  sections.extend(["### Prompt", ""])
  if prompt_section:
    sections.extend([prompt_section, ""])

  sections.extend(["### Result", ""])
  if parsed_result is not None and parsed_result.kql_result is not None:
    sections.extend([parsed_result.kql_result.explanation.strip(), ""])

  if parsed_result is not None:
    stats_table = render_stats_table(parsed_result.token_usage)
    if stats_table:
      sections.extend([stats_table, ""])

    rendered_queries = render_queries(parsed_result.queries)
    if rendered_queries:
      sections.extend([rendered_queries, ""])

  return sections


def build_report(args: DayReportArgs) -> str:
  """Build the final markdown report."""
  output_path = args.output or DAYS_DIR / f"day-{args.day_number}.md"
  parsed_result = (
    parse_result_json(args.result_json) if args.result_json is not None else None
  )

  sections: list[str] = [
    f"# Day {args.day_number}",
    "",
    build_intro(args.day_number, args.title, args.intro),
    "",
    "# Note",
    "",
    args.note.strip() if args.note else "",
    "",
    "# Gen AI Time",
    "",
  ]

  official_doc = render_official_doc(
    args.official_doc_label,
    args.official_doc_url,
  )
  if official_doc != "[]()":
    sections[4:4] = [
      "# Official Document",
      "",
      official_doc,
      "",
    ]

  summary_text = args.summary
  if not summary_text and parsed_result is not None and parsed_result.summary_text:
    summary_text = parsed_result.summary_text

  if parsed_result is not None and parsed_result.loop_result is not None:
    if summary_text and summary_text != parsed_result.summary_text:
      sections.extend([summary_text.strip(), ""])
    sections.extend(
      render_loop_attempts(
        loop_result=parsed_result.loop_result,
        output_path=output_path,
        prompt_file=args.prompt_file,
        prompt_text=args.prompt_text,
        embed_prompt=args.embed_prompt,
      )
    )
  else:
    sections.extend(
      render_single_attempt(
        output_path=output_path,
        prompt_file=args.prompt_file,
        prompt_text=args.prompt_text,
        embed_prompt=args.embed_prompt,
        parsed_result=parsed_result,
        summary_text=summary_text,
      )
    )

  links_text = render_links(args.link)
  if links_text:
    sections.extend(["# Links", "", links_text])

  return "\n".join(sections).rstrip() + "\n"


def should_write_report(args: DayReportArgs) -> bool:
  """Return whether the invocation includes enough inputs to write a report."""
  return any(
    [
      args.output is not None,
      args.intro is not None,
      args.note is not None,
      args.summary is not None,
      args.official_doc_label is not None,
      args.official_doc_url is not None,
      args.result_json is not None,
      bool(args.link),
      args.prompt_text is not None,
      args.embed_prompt,
      args.prompt_file is not None,
    ]
  )


def main() -> None:
  """Parse arguments and write the day report."""
  args = parse_args()
  APP_LOGGER.set_mode(args.log_mode)

  output_path = args.output or DAYS_DIR / f"day-{args.day_number}.md"
  write_report = should_write_report(args)
  total_token_usage = {"input": 0, "output": 0, "total": 0}
  try:
    if write_report:
      validate_report_inputs(args)

    prompt_file = args.prompt_file
    source_text: str | None = None
    if args.source_document is not None:
      source_text = load_text_file(args.source_document)
      prompt_file, prompt_token_usage = write_generated_prompt(
        day_number=args.day_number,
        title=args.title,
        source_document=args.source_document,
        prompt_output=args.prompt_output,
        prompt_prefix=args.prompt_prefix,
        model_provider=args.model_provider,
        model_name=args.model,
      )
      accumulate_token_usage(total_token_usage, prompt_token_usage)
      APP_LOGGER.info(f"Wrote prompt file to: {prompt_file}", stderr=True)
      APP_LOGGER.info(
        f"Prompt generation tokens: {format_token_usage(prompt_token_usage)}",
        stderr=True,
      )

    if prompt_file is not None and args.prompt_file is None:
      args.prompt_file = prompt_file

    if write_report and args.note is None and source_text:
      generated_note, note_token_usage = build_generated_note(
        title=args.title,
        source_document_text=source_text,
        model_provider=args.model_provider,
        model_name=args.model,
      )
      accumulate_token_usage(total_token_usage, note_token_usage)
      if generated_note:
        args.note = generated_note
      APP_LOGGER.info(
        f"Note generation tokens: {format_token_usage(note_token_usage)}",
        stderr=True,
      )

    if write_report:
      report = build_report(args)
      output_path.write_text(report, encoding="utf-8")
      APP_LOGGER.info(f"Wrote day report to: {output_path}", stderr=True)

    if total_token_usage["total"] > 0:
      APP_LOGGER.info(
        f"Final token usage: {format_token_usage(total_token_usage)}",
        stderr=True,
      )
  except Exception as exc:
    APP_LOGGER.error(f"Error: {exc}")
    sys.exit(1)


if __name__ == "__main__":
  main()
