## Makefile for managing Docker containers and scripts
.PHONY: help up down lint lint-fix convert list-targets

help: ## Show help message
	@grep -E '^[a-zA-Z_-]+:\s*##' $(MAKEFILE_LIST) | sed 's/:.*##\s*/: /'

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
