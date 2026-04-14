## Makefile for managing Docker containers and scripts
.PHONY: help up down lint lint-fix convert list-targets format new-day-% next-day n install-experimental-packages i install

help: ## Show help message
	@grep -E '^[a-zA-Z0-9_%\-]+:\s*##' $(MAKEFILE_LIST) | sed 's/:.*##\s*/: /'

up: ## Start the Docker containers in detached mode
	docker compose -f docker-compose.yml up -d

down: ## Stop the Docker containers
	docker compose -f docker-compose.yml down

format: ## Format the code using black
	ruff format --config ./scripts/pyproject.toml

lint: ## Run ruff linter on the scripts
	ruff check --config ./scripts/pyproject.toml

lint-fix: ## Run ruff linter with auto-fix on the scripts
	ruff check --fix --config ./scripts/pyproject.toml

convert: ## Convert UTC columns in the input file and save to the output file
	python3 ./scripts/convert_utc_columns.py $(input_file) -o $(output_file)

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

install: ## Install required packages for development
	pip install -r ./scripts/requirements.txt

install-experimental-packages: ## Install experimental packages (for testing purposes)
	pip uninstall kusto-mcp -y
	pip install ../kusto-mcp/dist/kusto_mcp-*-py3-none-any.whl

i: install-experimental-packages ## alias for install-experimental-packages

ai-time-%: ## Run the AI time script
	python scripts/generate_kql_query.py --prompt-file days/day-$*.prompt.md
