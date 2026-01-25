.PHONY: up down lint lint-fix

up:
	docker compose -f docker-compose.yml up -d

down:
	docker compose -f docker-compose.yml down

lint:
	ruff check --config ./scripts/pyproject.toml

lint-fix:
	ruff check --fix --config ./scripts/pyproject.toml
