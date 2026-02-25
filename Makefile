.PHONY: run test lint format build push

run:
	uvicorn app.main:app --reload --host 0.0.0.0 --port 5005

test:
	python -m pytest tests/ -q

lint:
	ruff check . && ruff format --check .

format:
	ruff check --fix . && ruff format .

build:
	podman build -t churchtools-local .

push:
	./build-and-push-docker-image.sh
