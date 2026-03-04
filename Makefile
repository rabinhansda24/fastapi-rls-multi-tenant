.PHONY: up down logs sh mig dbup dbdown

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
	alembic revision --autogenerate -m "$(m)"

dbup:
	sudo docker compose run --rm api alembic upgrade head

dbdown:
	sudo docker compose run --rm api alembic downgrade -1