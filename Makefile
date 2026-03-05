.PHONY: up down logs sh mig dbup dbdown test test-unit test-integration test-cov db-grant-createdb

# Usage: make mig m="create_ping"
m ?= migration

up:
	sudo docker compose up -d --build

down:
	sudo docker compose down

logs:
	sudo docker compose logs -f api

sh:
	sudo docker compose exec api sh

# Migrations (runs a one-off container)
mig:
	sudo docker compose run --rm api alembic revision --autogenerate -m "$(m)"

dbup:
	sudo docker compose run --rm api alembic upgrade head

dbdown:
	sudo docker compose run --rm api alembic downgrade -1

# One-time setup: grant CREATEDB to app_owner (requires superuser, cannot go through Alembic)
db-grant-createdb:
	sudo docker compose exec db psql -U postgres -c "ALTER ROLE app_owner CREATEDB;"

# Tests (run against a fresh isolated test DB, dropped after the run)
test:
	sudo docker compose --profile test run --rm test pytest -v

# Unit tests only — no DB interaction, fast feedback
test-unit:
	sudo docker compose --profile test run --rm test pytest app/core/tests app/utils/tests app/service/tests -v

# Integration tests only — exercises real DB + RLS
test-integration:
	sudo docker compose --profile test run --rm test pytest app/tests -v

# All tests with coverage report
test-cov:
	sudo docker compose --profile test run --rm test pytest --cov=app --cov-report=term-missing