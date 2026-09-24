# ---------------------------------------------------------------------------
# Warehouse & Inventory Management System — developer shortcuts
# ---------------------------------------------------------------------------
SHELL := /bin/bash
COMPOSE ?= docker compose
BACKEND := backend
FRONTEND := frontend

.DEFAULT_GOAL := help
.PHONY: help env up down restart logs ps build shell-backend shell-db migrate makemigrations createsuperuser test test-backend test-frontend lint lint-backend lint-frontend fmt typecheck check clean dev-services

help: ## Show available targets
	@grep -hE '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-18s\033[0m %s\n", $$1, $$2}'

env: ## Create .env from .env.example (fails if .env already exists)
	@test -f .env && echo ".env already exists" || (cp .env.example .env && echo "Created .env — fill in the secrets")

up: ## Start the full production-like stack (detached)
	$(COMPOSE) up -d --build
	@echo "API:    http://localhost/api/v1/health/"
	@echo "Docs:   http://localhost/api/v1/docs/ (if ENABLE_API_DOCS=true)"
	@echo "Web UI: http://localhost/"

down: ## Stop the stack
	$(COMPOSE) down

restart: ## Restart api + worker + beat
	$(COMPOSE) restart api worker beat

logs: ## Tail logs for all services
	$(COMPOSE) logs -f --tail=100

ps: ## Show service status
	$(COMPOSE) ps

build: ## Rebuild all images
	$(COMPOSE) build --pull

migrate: ## Apply database migrations inside the api container
	$(COMPOSE) exec api python manage.py migrate

makemigrations: ## Create new migrations inside the api container
	$(COMPOSE) exec api python manage.py makemigrations

createsuperuser: ## Create a Django admin user
	$(COMPOSE) exec api python manage.py createsuperuser

shell-backend: ## Open a Django shell
	$(COMPOSE) exec api python manage.py shell

shell-db: ## Open psql on the database
	$(COMPOSE) exec db psql -U $${POSTGRES_USER:-wims} -d $${POSTGRES_DB:-wims}

test: test-backend test-frontend ## Run backend + frontend test suites

test-backend: ## Run the Django test suite
	cd $(BACKEND) && ../.venv/bin/python manage.py test apps --settings=config.settings.test

test-frontend: ## Run the frontend test suite (vitest)
	cd $(FRONTEND) && npm run test

lint: lint-backend lint-frontend ## Lint everything

lint-backend: ## Ruff lint + format check
	cd $(BACKEND) && ../.venv/bin/ruff check . && ../.venv/bin/ruff format --check .

lint-frontend: ## TypeScript typecheck
	cd $(FRONTEND) && npm run typecheck

fmt: ## Auto-format the backend
	cd $(BACKEND) && ../.venv/bin/ruff format . && ../.venv/bin/ruff check . --fix

typecheck: ## Type check the frontend
	cd $(FRONTEND) && npm run typecheck

check: lint test ## Lint + test everything

dev-services: ## Start embedded PostgreSQL + Redis (no Docker required)
	.venv/bin/python scripts/dev_services.py

clean: ## Remove build artefacts and caches
	rm -rf $(FRONTEND)/dist $(FRONTEND)/coverage $(BACKEND)/staticfiles
	find . -type d -name __pycache__ -prune -exec rm -rf {} +
