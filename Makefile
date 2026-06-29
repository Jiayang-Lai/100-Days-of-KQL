## Makefile for managing Docker containers and Python tooling
.PHONY: help up down lint lint-fix convert list-targets format new-day-% next-day n install-experimental-packages i install trust ai-time-%

help: ## Show help message
	@grep -E '^[a-zA-Z0-9_%\-]+:\s*##' $(MAKEFILE_LIST) | sed 's/:.*##\s*/: /'

up: ## Start the Docker containers in detached mode
	docker compose -f docker-compose.yml up -d

trust: ## Get the generated local CA certificate from caddy and add it to the Kustainer container's trusted certificates
	docker compose cp caddy:/data/caddy/pki/authorities/local/root.crt ./docker/kustainer/root.ignore.crt
	docker exec kusto sh -c "cat /kustainer_cert/root.ignore.crt >> /etc/ssl/certs/ca-certificates.crt"

down: ## Stop the Docker containers
	docker compose -f docker-compose.yml down

format: ## Format the code using ruff
	uv run ruff format

lint: ## Run ruff linter on the scripts
	uv run ruff check

lint-fix: ## Run ruff linter with auto-fix on the scripts
	uv run ruff check --fix

convert: ## Convert UTC columns in the input file and save to the output file
	uv run python ./scripts/convert_utc_columns.py $(input_file) -o $(output_file)

new-day-%: ## Create new day markdown and KQL files (make new-day-<number>)
	@if [ -f "days/day-$*.md" ] || [ -f "days/day-$*.kql" ]; then echo "Error: day-$* already exists"; exit 1; fi
	@sed 's/{day_number}/$*/' templates/day.md > days/day-$*.md
	@touch days/day-$*.kql
	@echo "Created days/day-$*.md and days/day-$*.kql"
	@touch days/day-$*.prompt.md
	@echo "Created days/day-$*.prompt.md"

next-day: ## Create next day files (auto-detects the next day number)
	@next=$$(ls days/day-*.md 2>/dev/null | sed 's/.*day-\([0-9]*\)\.md/\1/' | sort -n | tail -1); \
	next=$${next:-0}; \
	next=$$((next + 1)); \
	$(MAKE) new-day-$$next

n: next-day ##alias next-day

install: ## Create/update the uv-managed virtual environment with dev tools
	uv sync --dev

install-experimental-packages: ## Install experimental packages (for testing purposes)
	uv sync --dev
	uv pip uninstall kusto-mcp -y
	uv pip install ../kusto-mcp/dist/kusto_mcp-*-py3-none-any.whl

i: install-experimental-packages ## alias for install-experimental-packages

ai-time-%: ## Run the AI time script to generate KQL query based on the prompt of the specified day
	uv run python scripts/generate_kql_query.py --prompt-file days/day-$*.prompt.md
