"""Generate KQL queries using an LLM agent with Kusto MCP server tools.

This script creates a langchain agent that uses MCP tools to:
1. List available Kusto tables
2. Get schema details for relevant tables
3. Generate KQL queries based on user input
"""

import argparse
import asyncio
import sys
from pathlib import Path
from typing import Any, TypedDict, cast

from agent_output import collect_token_usage, print_agent_events
from app_logger import LogMode, add_log_mode_argument, build_app_logger
from dotenv import load_dotenv
from fastmcp import Client
from kusto_mcp import FileSchemaLoader, configure_loader, mcp
from langchain.agents import create_agent
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_mcp_adapters.client import MultiServerMCPClient
from model_factory import (
  DEFAULT_MODEL_PROVIDER,
  create_chat_model,
)
from pydantic import BaseModel

load_dotenv()

# Schema directory relative to this script
SCHEMAS_DIR = Path(__file__).parent.parent / "schemas" / "tables"
SYSTEM_PROMPT_PATH = Path(__file__).parent / "prompts" / "kql_query.prompt.md"

# Configure the MCP server to use our local schema directory
configure_loader(FileSchemaLoader(schemas_dir=SCHEMAS_DIR))

# Load system prompt from markdown file
SYSTEM_PROMPT = SYSTEM_PROMPT_PATH.read_text(encoding="utf-8")
APP_LOGGER = build_app_logger("generate_kql_query")


class KQLQueryResult(BaseModel):
  """Structured output for KQL query generation."""

  request: str
  queries: list[str]
  explanation: str
  tables_used: list[str]
  token_usage: dict[str, int] | None = None


class AgentResponse(TypedDict):
  """Subset of the agent response used by this script."""

  messages: list[Any]
  structured_response: KQLQueryResult


class Args(argparse.Namespace):
  """Command-line arguments for this script."""

  query: str | None
  list_tables: bool
  log_mode: LogMode
  model: str
  model_provider: str
  verbose: bool
  prompt_file: Path | None


async def run_agent(
  user_request: str,
  *,
  model_provider: str,
  model_name: str,
  verbose: bool = False,
) -> KQLQueryResult:
  """Run the agent to generate a KQL query.

  Args:
    user_request: The user's query request
    model_provider: The LLM vendor/provider to use
    model_name: The model identifier within the selected provider
    verbose: If True, print AI messages to stderr

  Returns:
    KQLQueryResult with query, explanation, and metadata.
  """
  model = create_chat_model(provider=model_provider, model_name=model_name)

  # Connect to the MCP server and load tools
  client = MultiServerMCPClient(
    {
      "kusto tables": {
        "transport": "stdio",  # Local subprocess communication
        "command": "python",
        "args": ["scripts/start_mcp_server.py"],
      }
    }
  )

  # Load MCP tools into langchain format
  tools = await client.get_tools()
  # Create a ReAct agent with the MCP tools
  agent = create_agent(model, tools, response_format=KQLQueryResult)

  # Run the agent with the user's request
  messages = [
    SystemMessage(content=SYSTEM_PROMPT),
    HumanMessage(content=user_request),
  ]

  result = cast(AgentResponse, await agent.ainvoke({"messages": messages}))

  if verbose:
    print_agent_events(result["messages"], stream=sys.stderr)

  total_input_tokens, total_output_tokens = collect_token_usage(result["messages"])

  # Print token usage summary
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


async def async_main(args: Args) -> None:
  """Async main entry point."""
  if args.list_tables:
    # Quick mode: just list tables
    client = Client(mcp)
    async with client:
      result = await client.call_tool("list_tables", {})
      print(result)
    return

  # Single query mode - output structured JSON to stdout
  if args.query:
    APP_LOGGER.info("Running agent to generate KQL query...", stderr=True)
    try:
      result = await run_agent(
        args.query,
        model_provider=args.model_provider,
        model_name=args.model,
        verbose=args.verbose,
      )
      print(result.model_dump_json(indent=2))
    except Exception as e:
      APP_LOGGER.error(f"Error: {e}")
      sys.exit(1)
    return

  # Interactive mode - verbose output for user
  APP_LOGGER.info("Enter your query request (or 'quit' to exit):")
  while True:
    try:
      user_input = input("\n> ").strip()
    except EOFError:
      break

    if user_input.lower() in ("quit", "exit", "q"):
      APP_LOGGER.info("Goodbye!")
      break

    if not user_input:
      continue

    APP_LOGGER.info("\nRunning agent...", stderr=True)
    try:
      result = await run_agent(
        user_input,
        model_provider=args.model_provider,
        model_name=args.model,
        verbose=True,
      )
      print(f"\n{result.model_dump_json(indent=2)}")
    except Exception as e:
      APP_LOGGER.error(f"Error: {e}")


def main() -> None:
  """Run the KQL query generator."""
  parser = argparse.ArgumentParser(
    description="Generate KQL queries using an LLM agent with Kusto MCP tools"
  )
  add_log_mode_argument(parser)
  parser.add_argument(
    "query",
    nargs="?",
    help="Query request (if not provided, enters interactive mode)",
  )
  parser.add_argument(
    "--list-tables",
    action="store_true",
    help="List available tables and exit",
  )
  parser.add_argument(
    "--model-provider",
    default=DEFAULT_MODEL_PROVIDER,
    help=f"Model provider to use for the agent (default: {DEFAULT_MODEL_PROVIDER})",
  )
  parser.add_argument(
    "--model",
    help="Model name to use for the agent (defaults to default values per provider)",
  )
  parser.add_argument(
    "-v",
    "--verbose",
    action="store_true",
    help="Print verbose AI messages to stderr",
  )
  parser.add_argument(
    "-p",
    "--prompt-file",
    dest="prompt_file",
    type=Path,
    help="Read the prompt/request from a file and use it as the query",
  )
  args = parser.parse_args(namespace=Args())
  APP_LOGGER.set_mode(args.log_mode)

  # If a prompt file was provided, read it and use its contents as the query.
  if args.prompt_file is not None:
    try:
      prompt_file = args.prompt_file

      if not prompt_file.exists():
        APP_LOGGER.error(f"Prompt file not found: {prompt_file}")
        sys.exit(2)
      prompt_text = prompt_file.read_text(encoding="utf-8").strip()
      if not prompt_text:
        APP_LOGGER.error(f"Prompt file is empty: {prompt_file}")
        sys.exit(2)
      # Prompt file takes precedence over positional query argument
      args.query = prompt_text
    except Exception as e:
      APP_LOGGER.error(f"Failed to read prompt file: {e}")
      sys.exit(2)

  asyncio.run(async_main(args))


if __name__ == "__main__":
  main()
