# Introduction

This repository documents my 100 Days of KQL challenge work, including daily Kusto Query Language exercises, supporting notes, sample telemetry, and the tooling built around the project. In addition to the query content itself, the repository includes a local Docker-based lab environment powered by Kustainer, Jupyter, and Caddy for reproducible testing, along with an AI-assisted workflow that uses a local MCP server and schema-aware tooling to generate KQL queries from natural language prompts.

# Project Structure

```text
100-Days-of-KQL/
├── days/                # Daily challenge queries, notes, and prompt files
├── samples/             # Sample telemetry and CSV datasets
├── schemas/             # Local KQL table schema definitions
├── scripts/             # Automation, MCP server, and helper utilities
├── docker/              # Jupyter, Caddy, and Kustainer container assets
├── templates/           # Starter templates for new day files
├── docker-compose.yml   # Local lab environment definition
├── Makefile             # Common setup and workflow commands
└── README.md            # Project documentation and update log
```

The repository is organized into a few main areas:

- `days`: daily KQL challenge content, including the query files, notes, and prompt files used for AI-assisted query generation on later days.
- `samples`: sample telemetry and CSV data used by the KQL queries. Microsoft has a great repository with a comprehensive list of sample log [here](https://github.com/Azure/Azure-Sentinel/tree/master/Sample%20Data).
- `schemas`: local table schema definitions used by the MCP-based query generation workflow.
- `scripts`: helper utilities and automation, including CSV datetime normalization, the AI-powered KQL query generator, the local MCP server entrypoint, and prompt/configuration files.
- `docker`: container-specific assets for the local lab environment, including Jupyter, Caddy, and Kustainer-related files.
- `templates`: starter templates used when creating new day files.

Supporting files at the repository root include:

- `docker-compose.yml`: defines the local lab environment.
- `Makefile`: provides shortcuts for common setup and workflow commands.
- `README.md`: project documentation and update log.

Within `days/`, the markdown file types have different roles:
- `day-X.md`: the human-readable day report / journal entry
- `day-X.kql`: the final KQL query or exercise content for that day
- `day-X.prompt.md`: the prompt input used by the AI-assisted query workflow
- `day-X.source.md`: the source write-up or incident material used to generate a prompt file

# Setup

Instead of relying on Actual Sentinel instance or Azure Data Explorer, this project uses an ADX emulator, aka Kustainer. Please find more information from [Microsoft site](https://learn.microsoft.com/en-us/azure/data-explorer/kusto-emulator-overview). According to Microsoft:

> The Kusto emulator is a local environment that encapsulates the query engine. You can use the environment to facilitate local development and automated testing. Since the environment runs locally, it doesn't require provisioning Azure services or incurring any cost.

I have created a docker compose file based on the one from [Tao of Mac](https://taoofmac.com/space/blog/2024/06/28/2100) (thank you Taoofmac!), with the only change of using a minimal Jupyter notebook image rather than the PyTorch one.

To set up the local environment, first install the Python tooling with `make install` (this uses `uv` and creates a repo-local `.venv`), then run `make up trust`. The Kustainer uses a volume for persistent storage, but you have to manually load the data after each restart or new Kustainer container creation.

After the environment is up and running, run command `docker logs <your Jupyter container id>` to get the access URL with token. Then follow this [guide](https://learn.microsoft.com/en-us/azure-data-studio/notebooks/notebooks-kqlmagic) to install KqlMagic extension for Jupyter notebook. Here is the command (from Tao of Mac) to install KqlMagic and activate it:

```python
!pip install kqlmagic
%reload_ext Kqlmagic 
%kql --activate_kernel
```

To connect to the Kustainer, run this command:

```python
azureDataExplorer://anonymous;cluster='http://kusto:8080';database='NetDefaultDB';alias='default'
```

Vola, your local lab environment is now ready for KQL queries :).

Or is it?

When I tried the commands above, running KQL queries return an error of `KeyError: 'DEFAULT'`. After diving into [GitHub issues](https://github.com/microsoft/jupyter-Kqlmagic/issues/114) and posts, I found out that one of the dependencies (prettytable) has a breaking change that KqlMagic never accommodates. Therefore, as the comment in the issue suggests, we have to install an older version of prettytable by running command `!pip install kqlmagic==3.11.0` before running other installation command.

TL;DR: open a new notebook and run this command instead:

```python
!pip install prettytable==3.11.0
!pip install kqlmagic
%reload_ext Kqlmagic 
%kql --activate_kernel
%kql azureDataExplorer://anonymous;cluster='http://kusto:8080';database='NetDefaultDB';alias='default'
```

To destroy the environment, run `make down` (you have to specifically remove the volume after this command).

# 2026-01-20 Update

## KqlMagic prettytable Issue and PR

While working on the setup, I discovered that KqlMagic breaks due to breaking changes in the `prettytable` dependency. This causes the `KeyError: 'DEFAULT'` error mentioned in the Setup section. I have submitted a PR to address this issue: [microsoft/jupyter-Kqlmagic#121](https://github.com/microsoft/jupyter-Kqlmagic/pull/121). Until the PR is merged, the workaround of installing an older version of prettytable (`pip install prettytable==3.11.0`) is necessary.

# 2026-01-25 Update

## convert_utc_columns.py

When exporting query result from Azure portal, the columns with datetime type will be exported with a name suffix of ` [UTC]` and a non ISO8601 compliant datetime string in a CSV file. This causes issues when using `externaldata` to import from this export. (Yes I know it is possible to query and export the data with the ISO8601 datetime string via [azure-monitor-query](https://pypi.org/project/azure-monitor-query/))

Therefore, I wrote a quick script for QoL automation.

Added a utility script `scripts/convert_utc_columns.py` to process CSV files with datetime columns that have `[UTC]` in their column names. The script performs two main operations:

1. **DateTime Conversion**: Converts non-standard datetime formats (e.g., `M/D/YYYY, h:mm:ss.fff AM/PM`) to ISO 8601 format (`YYYY-MM-DDTHH:MM:SS.fffZ`)
2. **Column Renaming**: Removes the `[UTC]` suffix from column names after conversion

**Usage:**
```bash
# Convert with output file
uv run python scripts/convert_utc_columns.py samples/input.csv -o samples/output.csv

# Convert in-place (prompts for confirmation)
uv run python scripts/convert_utc_columns.py samples/input.csv
```

**Features:**
- Automatically detects all columns containing `[UTC]` (**the space before the square bracket must be removed**) in their names
- Supports reusable functions for integration with other scripts:
  - `convert_utc_columns(input_file, output_file)`: File-based conversion
  - `rename_utc_columns(df)`: In-memory dataframe column renaming

Some sample files come from Tom's repository [here](https://github.com/tom564/100_days_kql_2026/blob/main/Datasets) (thank you Tom!).

# 2026-04-10 Update

## generate_kql_query.py

Added an AI-powered KQL query generator that uses an LLM agent with Kusto MCP (Model Context Protocol) tools. The script connects to a local MCP server to access table schemas and generates KQL queries based on natural language requests.

**Features:**
- Uses Claude (claude-haiku-4-5) with structured output via Pydantic models
- Automatically discovers available tables and their schemas
- Returns structured JSON output for automation consumption
- Supports both interactive mode and single-query mode

**Usage:**
```bash
# Single query mode - outputs structured JSON to stdout
uv run python scripts/generate_kql_query.py "get devices that reached out to 1.1.1.1"

# With verbose AI reasoning output
uv run python scripts/generate_kql_query.py -v "get 10 windows VMs"

# Interactive mode
uv run python scripts/generate_kql_query.py

# List available tables
uv run python scripts/generate_kql_query.py --list-tables
```

Additional usage:

```bash
# Read the prompt/request from a file (takes precedence over the positional query)
uv run python scripts/generate_kql_query.py --prompt-file days/day-25.prompt.md
# Short flag
uv run python scripts/generate_kql_query.py -p days/day-25.prompt.md
```

Notes:
- If `--prompt-file` is provided, its contents are used as the query request and override the positional `query` argument.
- The script prints structured JSON to stdout and diagnostic/verbose output to stderr (use `-v` for verbose AI reasoning).

**Output Format:**
The script returns a `KQLQueryResult` Pydantic model with the following fields:
```json
{
  "request": "get 10 windows VM",
  "queries": ["DeviceInfo\n| where OSPlatform startswith \"Windows\"\n| limit 10"],
  "explanation": "This query retrieves 10 Windows devices...",
  "tables_used": ["DeviceInfo"],
  "token_usage": {
    "input_tokens": 5862,
    "output_tokens": 317,
    "total_tokens": 6179
  }
}
```

**Output Redirection:**
- **stdout**: Structured JSON results (for piping/automation)
- **stderr**: Status messages, token usage, verbose AI output (with `-v`)

**Requirements:**
- `ANTHROPIC_API_KEY` environment variable set
- Dependencies: `langchain`, `langchain-anthropic`, `langchain-mcp-adapters`, `pydantic`
- `kusto-mcp` package (must be built locally, see below)

**Installing kusto-mcp:**

The `kusto-mcp` package is now published to PyPI, so by simply running `make install` the package will be installed into the `uv`-managed `.venv`.

But if you still wish to build the package locally from the sibling [kusto-mcp](https://github.com/Jiayang-Lai/kusto-mcp) repository here is the snippet to do so:

```bash
# Clone the kusto-mcp repo as a sibling directory
cd ..
git clone https://github.com/Jiayang-Lai/kusto-mcp.git
cd kusto-mcp

git checkout feature/mvp

# Build the wheel
uv build

# Return to this project and install
cd ../100-Days-of-KQL
make install-experimental-packages
# or manually:
# uv pip install ../kusto-mcp/dist/kusto_mcp-0.1.0-py3-none-any.whl
```

# 2026-04-19 Update

## Summary of changes

- **Jupyter notebook persistency & starter notebook**: Jupyter data and sessions are now persisted through the project's Docker volumes so notebooks survive container restarts. A lightweight starter notebook has been added for quick onboarding: [docker/jupyter/workbench.ipynb](docker/jupyter/workbench.ipynb). Use this notebook to quickly connect to the local Kustainer instance and try example queries.
- **docker compose networking refactor**: The docker compose setup has been refactored to create a dedicated internal network for service-to-service communication. This makes it easier for Kustainer to retrieve data from other local services (for example the local file server) without exposing those services publicly.
- **Caddy introduced as local file server for Kustainer**: A Caddy container is included and configured to serve mounted files within the same docker network (see [docker/caddy/Caddyfile](docker/caddy/Caddyfile)). Kustainer can now access local sample data and schema files over HTTPS which simplifies testing `externaldata` and related workflows. You can now access the web GUI of the file server [here](https://localhost:4433/).
- **New Make target: `trust`**: A new make target `trust` was added to streamline enabling TLS-based file retrieval. Run `make trust` to append the Caddy CA certificate into the Kustainer container's trust store so Kustainer trusts the local Caddy HTTPS endpoint. This avoids manual certificate installation and enables secure `https://` access to local files from within the cluster.

# 2026-06-29 Update

## execute_kql_query.py

Added a minimal query execution harness for the local Kustainer instance.

**Usage:**
```bash
# Run a generated table query
uv run python scripts/execute_kql_query.py --table Table_0

# Run raw KQL directly
uv run python scripts/execute_kql_query.py --query 'print banner=strcat("Hello", ", ", "World!")'

# Dump a table schema in the local table.json-compatible format
uv run python scripts/execute_kql_query.py --schema-dump --table Table_0
```

# 2026-07-03 Update

## generate_mock_logs.py

Added a companion mock log generator that uses the same Kusto MCP schema tooling, but instead of producing KQL it produces schema-aligned mock Sentinel rows from IOC context.

**Features:**
- Accepts repeated `--table` flags to constrain generation, or auto-discovers all MCP tables when omitted
- Reads IOC context from inline text or a document with `--ioc-file`
- Uses Kusto MCP schema lookups before generating any rows
- Returns structured JSON grouped by table for easier downstream conversion
- Can also write a bundle under `samples/generated_mock_logs` with raw JSON and per-table CSVs
- Can optionally generate `bootstrap.kql` with `externaldata(...)` statements for the bundle CSVs

**Usage:**
```bash
# Generate mock logs from an IOC document
uv run python scripts/generate_mock_logs.py \
  --table DeviceNetworkEvents \
  --table DeviceFileEvents \
  --table DeviceProcessEvents \
  --ioc-file days/day-29.prompt.md

# Let the script consider all available MCP tables and pick the suitable ones
uv run python scripts/generate_mock_logs.py \
  --ioc-file days/day-29.prompt.md

# Inline IOC text
uv run python scripts/generate_mock_logs.py \
  --table DeviceNetworkEvents \
  --table DeviceFileEvents \
  "Generate mock logs for a downloader that reaches out to 142.11.206.73 and writes 6202033.ps1"

# Verbose mode with a custom target row count
uv run python scripts/generate_mock_logs.py \
  --table DeviceNetworkEvents \
  --table DeviceFileEvents \
  --rows-per-table 2 \
  --ioc-file days/day-29.prompt.md \
  -v

# Also write Kusto-ready CSVs and the raw JSON response under samples/
uv run python scripts/generate_mock_logs.py \
  --table DeviceNetworkEvents \
  --table DeviceFileEvents \
  --table DeviceProcessEvents \
  --ioc-file days/day-29.prompt.md \
  --write-files \
  --output-name axios-iocs

# Also generate bootstrap.kql for Kustainer ingestion through Caddy
uv run python scripts/generate_mock_logs.py \
  --table DeviceNetworkEvents \
  --table DeviceFileEvents \
  --table DeviceProcessEvents \
  --ioc-file days/day-29.prompt.md \
  --write-files \
  --write-bootstrap-kql \
  --bootstrap-base-url https://caddy \
  --output-name axios-iocs
```

Notes:
- `--ioc-file` takes precedence over inline IOC text.
- If `--table` is omitted, the script loads all available tables from `kusto-mcp list_tables` and lets the agent choose the relevant ones.
- The agent may skip allowed tables that do not fit the IOC scenario.
- The script prints structured JSON to stdout and diagnostics to stderr.
- `--write-files` creates a folder under `samples/generated_mock_logs` containing `mock_logs.raw.json` plus one CSV per generated table.
- `--write-bootstrap-kql` adds `bootstrap.kql` to that same folder, pointing at the generated CSVs through the configured base URL.

## run_detection_agent_loop.py

Added an orchestration script that takes a prompt file and runs an end-to-end validation loop:
- selects relevant tables for the scenario
- generates mock logs
- writes a mock-log bundle and `bootstrap.kql`
- generates KQL query candidates
- executes those queries against the generated mock data
- asks an evaluation agent whether the criteria are met or whether the next iteration should refine the request

**Usage:**
```bash
uv run python scripts/run_detection_agent_loop.py \
  days/day-30.prompt.md \
  --max-iterations 3 \
  --rows-per-table 3 \
  --bootstrap-base-url https://caddy

# Reuse an existing mock-log bundle and rerun only the KQL/evaluation loop
uv run python scripts/run_detection_agent_loop.py \
  days/day-30.prompt.md \
  --reuse-mock-log-bundle samples/generated_mock_logs/day-30 \
  --max-iterations 3
```

Notes:
- The script always writes a mock-log bundle because query execution depends on the generated CSV files and bootstrap KQL.
- If `--reuse-mock-log-bundle` is provided, the script reuses that bundle's `mock_logs.raw.json` and `bootstrap.kql` and skips table selection plus mock-log generation.
- The final stdout payload is structured JSON summarizing table selection, bundle location, loop iterations, evaluator feedback, and the final accepted query if one is found.

## write_day_report.py

Added a report helper that can automate two adjacent tasks for a new day:
- generate `day-X.prompt.md` from an initial source document that explains the topic and includes the IOC material
- generate a `day-X.md` report in the same house style used by the existing day notes

The prompt-generation flow is designed to feed directly into `run_detection_agent_loop.py`. It wraps the source document in a prompt that tells the query-generation workflow to extract IOC values, restore defanged indicators, and compose a complete KQL detection query.

**Usage:**
```bash
# Generate only day-X.prompt.md from a source document
uv run python scripts/write_day_report.py \
  --day-number 30 \
  --title "the Browser Syncjacking compromise" \
  --source-document days/day-30.source.md

# Generate a prompt file at an explicit location
uv run python scripts/write_day_report.py \
  --day-number 30 \
  --title "the mini Shai-Hulud compromise" \
  --source-document days/day-30.source.md \
  --prompt-output days/day-30.prompt.md

# Generate a report from a loop result and reference the prompt file
uv run python scripts/write_day_report.py \
  --day-number 30 \
  --title "the Browser Syncjacking compromise" \
  --note "A short note about the case goes here." \
  --official-doc-label "Incident write-up" \
  --official-doc-url "https://example.com/report" \
  --prompt-file days/day-30.prompt.md \
  --result-json samples/generated_mock_logs/day-30-prompt/loop_result.json \
  --output days/day-30.md

# Generate both the prompt file and the report in one run
uv run python scripts/write_day_report.py \
  --day-number 30 \
  --title "the Browser Syncjacking compromise" \
  --source-document days/day-30.source.md \
  --note "A short note about the case goes here." \
  --official-doc-label "Incident write-up" \
  --official-doc-url "https://example.com/report" \
  --result-json samples/generated_mock_logs/day-30-prompt/loop_result.json \
  --output days/day-30.md
```

Notes:
- When `--source-document` is provided, the script writes a prompt file to `days/day-X.prompt.md` by default.
- `--prompt-output` overrides the default prompt destination.
- `--prompt-prefix` can be used to override the default prompt instructions if a day needs a more specific framing.
- If you only provide prompt-generation inputs, the script runs in prompt-only mode and does not create a day report.
- If you also provide report-related inputs such as `--result-json`, `--note`, or `--output`, the script can generate the prompt file and the day report together.

# To-dos

- [ ] Provide KQL operator and function usage/syntax as tool within kusto-mcp.
- [X] Expose local file through another container within the same docker network to enable rapid iteration of test log (compared to committing to remote repository).
  - [X] Use caddy to expose the mounted directory within the docker network.
  - [X] Load custom config (quite sure there would be a container)
- [X] Create function for agent to run query against local Kustainer and get return.
- [X] Create an agent harness to fully automate the process of generating KQL query.
  - [X] Provide system prompt and initial message.
  - [X] Provide agent with access to run query within Kustainer.
  - [X] Implement loop mechanism to give agent autonomy to generate and improve query to meet requirements.
