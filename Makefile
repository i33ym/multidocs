# ==================================================================================== #
# HELPERS
# ==================================================================================== #

## help: print this help message
.PHONY: help
help:
	@echo 'Usage:'
	@sed -n 's/^## //p' ${MAKEFILE_LIST} | column -t -s ':' | sed 's/^/  /'

.PHONY: confirm
confirm:
	@echo -n 'Are you sure? [y/N] ' && read ans && [ $${ans:-N} = y ]

# ==================================================================================== #
# DEVELOPMENT
# ==================================================================================== #

## run: run the application
.PHONY: run
run:
	uv run python main.py

## run/debug: run with debug mode and hot reload
.PHONY: run/debug
run/debug:
	APP_DEBUG=True uv run python main.py

## index: index documentation into the vector store
.PHONY: index
index:
	uv run python scripts/index.py

## mcp: run standalone MCP server (stdio)
.PHONY: mcp
mcp:
	uv run python scripts/mcp_server.py

## db/create: create the database and enable pgvector
.PHONY: db/create
db/create:
	createdb multidocs
	psql -d multidocs -c "CREATE EXTENSION IF NOT EXISTS vector"

## db/psql: connect to the database using psql
.PHONY: db/psql
db/psql:
	psql -d multidocs

# ==================================================================================== #
# QUALITY CONTROL
# ==================================================================================== #

## lint: run ruff linter
.PHONY: lint
lint:
	uv run ruff check .

## format: format code with ruff
.PHONY: format
format:
	uv run ruff format .

## format/check: check code formatting without changes
.PHONY: format/check
format/check:
	uv run ruff format --check .

## typecheck: run mypy type checker
.PHONY: typecheck
typecheck:
	uv run mypy app/ main.py --ignore-missing-imports

## test: run all tests
.PHONY: test
test:
	uv run pytest tests/ -v

## audit: run all quality checks (lint, format, typecheck, test)
.PHONY: audit
audit: lint format/check typecheck test

# ==================================================================================== #
# SETUP
# ==================================================================================== #

## setup: install dependencies, create db, index docs
.PHONY: setup
setup: confirm
	uv sync
	@echo 'Copying .env.example to .env (if not exists)...'
	cp -n .env.example .env || true
	@echo 'Creating database...'
	createdb multidocs 2>/dev/null || true
	psql -d multidocs -c "CREATE EXTENSION IF NOT EXISTS vector" 2>/dev/null || true
	@echo 'Indexing documents...'
	uv run python scripts/index.py
	@echo 'Setup complete. Edit .env with your credentials, then run: make run'

# ==================================================================================== #
# PRODUCTION
# ==================================================================================== #

## prod/reindex: force reindex via admin API
.PHONY: prod/reindex
prod/reindex:
	@test -n "$(ADMIN_KEY)" || (echo 'Usage: make prod/reindex ADMIN_KEY=your-key' && exit 1)
	@test -n "$(HOST)" || (echo 'Usage: make prod/reindex HOST=https://your-domain.com ADMIN_KEY=your-key' && exit 1)
	curl -X POST $(HOST)/api/admin/reindex -H "Authorization: Bearer $(ADMIN_KEY)"

## prod/health: check production health
.PHONY: prod/health
prod/health:
	@test -n "$(HOST)" || (echo 'Usage: make prod/health HOST=https://your-domain.com' && exit 1)
	curl -s $(HOST)/api/health | python3 -m json.tool
