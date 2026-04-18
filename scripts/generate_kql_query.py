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

from dotenv import load_dotenv
from fastmcp import Client
from kusto_mcp import FileSchemaLoader, configure_loader, mcp
from langchain.agents import create_agent
from langchain_anthropic import ChatAnthropic
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_mcp_adapters.client import MultiServerMCPClient
from pydantic import BaseModel

load_dotenv()

# Schema directory relative to this script
SCHEMAS_DIR = Path(__file__).parent.parent / "schemas" / "tables"
SYSTEM_PROMPT_PATH = Path(__file__).parent / "system_prompt.md"

# Configure the MCP server to use our local schema directory
configure_loader(FileSchemaLoader(schemas_dir=SCHEMAS_DIR))

# Load system prompt from markdown file
SYSTEM_PROMPT = SYSTEM_PROMPT_PATH.read_text()


class KQLQueryResult(BaseModel):
  """Structured output for KQL query generation."""

  request: str
  queries: list[str]
  explanation: str
  tables_used: list[str]


async def run_agent(user_request: str, verbose: bool = False) -> KQLQueryResult:
  """Run the agent to generate a KQL query.

  Args:
    user_request: The user's query request
    verbose: If True, print AI messages to stderr

  Returns:
    KQLQueryResult with query, explanation, and metadata.
  """
  model = ChatAnthropic(model="claude-haiku-4-5-20251001")

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

  result = await agent.ainvoke({"messages": messages})

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
            if block.get("type") == "text":
              print(block["text"], file=sys.stderr)
            elif block.get("type") == "tool_use":
              tool_name = block.get("name", "unknown")
              tool_input = block.get("input", {})
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


async def async_main(args: argparse.Namespace) -> None:
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
      result = await run_agent(args.query, verbose=args.verbose)
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
      result = await run_agent(user_input, verbose=True)
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
  args = parser.parse_args()

  # If a prompt file was provided, read it and use its contents as the query.
  if getattr(args, "prompt_file", None):
    try:
      if not args.prompt_file.exists():
        print(f"Prompt file not found: {args.prompt_file}", file=sys.stderr)
        sys.exit(2)
      prompt_text = args.prompt_file.read_text(encoding="utf-8").strip()
      if not prompt_text:
        print(f"Prompt file is empty: {args.prompt_file}", file=sys.stderr)
        sys.exit(2)
      # Prompt file takes precedence over positional query argument
      args.query = prompt_text
    except Exception as e:
      print(f"Failed to read prompt file: {e}", file=sys.stderr)
      sys.exit(2)

  asyncio.run(async_main(args))


if __name__ == "__main__":
  main()
