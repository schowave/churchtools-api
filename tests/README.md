# Tests

Unit and API tests for the app. External calls to ChurchTools are mocked; no network access or credentials are needed.

## Running

```bash
mise run test   # quick run
mise run cov    # with coverage report (terminal + coverage.xml)
```

For an HTML coverage report:

```bash
pytest --cov=app tests/ --cov-report=html
```

## CI

- `test-and-build.yml` runs lint and tests with coverage on every push to `main` and on pull requests, uploads coverage to Codecov, and builds the Docker image (without pushing).
- `release.yml` is triggered manually. It runs lint and tests, bumps the version in `pyproject.toml`, tags the release, and pushes the Docker image to Docker Hub.
