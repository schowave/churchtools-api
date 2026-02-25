.PHONY: run test lint format build push preview

PYTHON := venv/bin/python

run:
	$(PYTHON) -m uvicorn app.main:app --reload --host 0.0.0.0 --port 5005

test:
	$(PYTHON) -m pytest tests/ -q

lint:
	$(PYTHON) -m ruff check . && $(PYTHON) -m ruff format --check .

format:
	$(PYTHON) -m ruff check --fix . && $(PYTHON) -m ruff format .

build:
	podman build -t churchtools-local .

push:
	./build-and-push-docker-image.sh

preview:
	$(PYTHON) scripts/preview_pdf.py && open app/saved_files/*_Termine.pdf
