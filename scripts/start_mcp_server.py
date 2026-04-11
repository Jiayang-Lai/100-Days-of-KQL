"""Test script for the Kusto MCP server."""

from pathlib import Path

from dotenv import load_dotenv
from fastmcp.utilities.logging import configure_logging
from kusto_mcp import FileSchemaLoader, configure_loader, mcp

load_dotenv()
configure_logging(level="WARNING")

# Schema directory relative to this script
SCHEMAS_DIR = Path(__file__).parent.parent / "schemas" / "tables"
SYSTEM_PROMPT_PATH = Path(__file__).parent / "system_prompt.md"

# Configure the MCP server to use our local schema directory
configure_loader(FileSchemaLoader(schemas_dir=SCHEMAS_DIR))

mcp.run(show_banner=False)
