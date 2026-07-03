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

from dotenv import load_dotenv
from fastmcp import Client
from kusto_mcp import FileSchemaLoader, configure_loader, mcp
from langchain.agents import create_agent
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_mcp_adapters.client import MultiServerMCPClient
from model_factory import (
  DEFAULT_MODEL_NAME,
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


class KQLQueryResult(BaseModel):
  """Structured output for KQL query generation."""

  request: str
  queries: list[str]
  explanation: str
  tables_used: list[str]


class TextBlock(TypedDict):
  """Typed text content block returned by the model."""

  type: str
  text: str


class ToolUseBlock(TypedDict, total=False):
  """Typed tool-use content block returned by the model."""

  type: str
  name: str
  input: dict[str, Any]


class AgentResponse(TypedDict):
  """Subset of the agent response used by this script."""

  messages: list[Any]
  structured_response: KQLQueryResult


class Args(argparse.Namespace):
  """Command-line arguments for this script."""

  query: str | None
  list_tables: bool
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

  # Track token usage
  total_input_tokens = 0
  total_output_tokens = 0

  # Print all AI messages from the conversation
  for msg in result["messages"]:
    if isinstance(msg, AIMessage):
      content = msg.content
      if verbose:
        if isinstance(content, str):
          print(content, file=sys.stderr)
        elif isinstance(content, list):
          for block in content:
            if not isinstance(block, dict):
              continue

            block_type = block.get("type")
            if block_type == "text":
              text_block = cast(TextBlock, block)
              print(text_block["text"], file=sys.stderr)
            elif block_type == "tool_use":
              tool_block = cast(ToolUseBlock, block)
              tool_name = tool_block.get("name", "unknown")
              tool_input = tool_block.get("input", {})
              print(f"[Tool Call: {tool_name}({tool_input})]", file=sys.stderr)

      # Aggregate token usage from response metadata
      if hasattr(msg, "usage_metadata") and msg.usage_metadata:
        total_input_tokens += msg.usage_metadata.get("input_tokens", 0)
        total_output_tokens += msg.usage_metadata.get("output_tokens", 0)

  # Print token usage summary
  total_tokens = total_input_tokens + total_output_tokens
  token_msg = (
    f"[Tokens: {total_input_tokens} input + {total_output_tokens} output = "
    f"{total_tokens} total]"
  )
  print(token_msg, file=sys.stderr)
  return result["structured_response"]


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
    print("Running agent to generate KQL query...", file=sys.stderr)
    try:
      result = await run_agent(
        args.query,
        model_provider=args.model_provider,
        model_name=args.model,
        verbose=args.verbose,
      )
      print(result.model_dump_json(indent=2))
    except Exception as e:
      print(f"Error: {e}", file=sys.stderr)
      sys.exit(1)
    return

  # Interactive mode - verbose output for user
  print("Enter your query request (or 'quit' to exit):")
  while True:
    try:
      user_input = input("\n> ").strip()
    except EOFError:
      break

    if user_input.lower() in ("quit", "exit", "q"):
      print("Goodbye!")
      break

    if not user_input:
      continue

    print("\nRunning agent...", file=sys.stderr)
    try:
      result = await run_agent(
        user_input,
        model_provider=args.model_provider,
        model_name=args.model,
        verbose=True,
      )
      print(f"\n{result.model_dump_json(indent=2)}")
    except Exception as e:
      print(f"Error: {e}", file=sys.stderr)


def main() -> None:
  """Run the KQL query generator."""
  parser = argparse.ArgumentParser(
    description="Generate KQL queries using an LLM agent with Kusto MCP tools"
  )
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
    help=(
      "Model provider to use for the agent "
      f"(default: {DEFAULT_MODEL_PROVIDER})"
    ),
  )
  parser.add_argument(
    "--model",
    default=DEFAULT_MODEL_NAME,
    help=f"Model name to use for the agent (default: {DEFAULT_MODEL_NAME})",
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

  # If a prompt file was provided, read it and use its contents as the query.
  if args.prompt_file is not None:
    try:
      prompt_file = args.prompt_file

      if not prompt_file.exists():
        print(f"Prompt file not found: {prompt_file}", file=sys.stderr)
        sys.exit(2)
      prompt_text = prompt_file.read_text(encoding="utf-8").strip()
      if not prompt_text:
        print(f"Prompt file is empty: {prompt_file}", file=sys.stderr)
        sys.exit(2)
      # Prompt file takes precedence over positional query argument
      args.query = prompt_text
    except Exception as e:
      print(f"Failed to read prompt file: {e}", file=sys.stderr)
      sys.exit(2)

  asyncio.run(async_main(args))


if __name__ == "__main__":
  main()
