.PHONY: install dev api worker test lint format typecheck migrate migration docker-up docker-down
install:
	python -m pip install --require-hashes -r requirements-dev.lock
	python -m pip install --no-deps -e .
dev:
	python -m uvicorn app.main:app --reload --no-access-log
api:
	python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --no-access-log
worker:
	python -m app.workers.main
test:
	python -m pytest
lint:
	python -m ruff check .
	python -m ruff format --check .
format:
	python -m ruff format .
typecheck:
	python -m mypy app
migrate:
	python -m alembic upgrade head
migration:
	python -m alembic revision --autogenerate -m "$(name)"
docker-up:
	docker compose up --build -d
docker-down:
	docker compose down
