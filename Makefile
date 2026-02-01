## Makefile for managing Docker containers and scripts
.PHONY: help up down lint lint-fix convert list-targets new-day-%

help: ## Show help message
	@grep -E '^[a-zA-Z0-9_%\-]+:\s*##' $(MAKEFILE_LIST) | sed 's/:.*##\s*/: /'

up: ## Start the Docker containers in detached mode
	docker compose -f docker-compose.yml up -d

down: ## Stop the Docker containers
	docker compose -f docker-compose.yml down

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
