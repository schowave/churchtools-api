.PHONY: run run-docker test lint format build push

PYTHON := venv/bin/python

run:
	CHURCHTOOLS_BASE=$${CHURCHTOOLS_BASE:-$$(grep -s CHURCHTOOLS_BASE .env | cut -d= -f2)} \
	$(PYTHON) -m alembic upgrade head && \
	$(PYTHON) -m uvicorn app.main:app --reload --host 0.0.0.0 --port 5005

test:
	$(PYTHON) -m pytest tests/ -q

lint:
	$(PYTHON) -m ruff check . && $(PYTHON) -m ruff format --check .

format:
	$(PYTHON) -m ruff check --fix . && $(PYTHON) -m ruff format .

run-docker:
	podman run --rm -p 5005:5005 -v ./data:/app/data \
		-e CHURCHTOOLS_BASE=$${CHURCHTOOLS_BASE:-$$(grep -s CHURCHTOOLS_BASE .env | cut -d= -f2)} \
		-e DB_PATH=/app/data/churchtools.db \
		churchtools-local

build:
	podman build -t churchtools-local .

push:
	./build-and-push-docker-image.sh

