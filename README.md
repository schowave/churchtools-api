# ChurchTools API

This repository provides a user-friendly interface to access the ChurchTools API.

It was created to fulfill the need of displaying all appointments from [evkila.de](https://www.evkila.de/) on a single PDF file or as multiple JPEG images.

## Features

### Main Dashboard with Multiple Functions
![Overview Dashboard](images/overview.png)

### Calendar Selection
Select one or more public calendars to view and manage appointments:
![Calendar Selection](images/calendars.png)

### Export Options
Generate formatted PDF documents or JPEG images with customizable styling:
![Export Options](images/formatting.png)

### Output Example
Example of a generated appointment list:
![Result Example](images/result.png)

## Setup Instructions

### Prerequisites

- Python 3.12+
- Podman or Docker (for containerized deployment)

### Configuration

Copy the example environment file and fill in your values:

```bash
cp .env.example .env
```

```env
CHURCHTOOLS_BASE=your-instance.church.tools
DB_PATH=your-instance.db
```

### Local Development

```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements-dev.txt
make run
```

Access the application at [http://127.0.0.1:5005/](http://127.0.0.1:5005/)

### Available Make Commands

| Command       | Description                                  |
|---------------|----------------------------------------------|
| `make run`    | Start dev server with auto-reload            |
| `make test`   | Run test suite                               |
| `make lint`   | Check code style with ruff                   |
| `make format` | Auto-fix code style                          |
| `make build`  | Build container image locally                |
| `make push`   | Build and push multi-arch image to Docker Hub|

## Docker / Podman Deployment

### Quick start with Compose

```bash
podman compose up        # or: docker compose up
```

This uses `compose.yml` to build the image, expose port 5005, mount `./data` for the SQLite database, and load variables from `.env`.

### Run locally without Compose

```bash
./run_docker.sh
```

The script auto-detects Podman or Docker, builds the image, and starts a container with your `.env` configuration.

### Build and push to Docker Hub

```bash
./build-and-push-docker-image.sh
```

The script auto-detects Podman or Docker, checks your Docker Hub login, and builds a multi-architecture image (amd64 + arm64). The version is defined at the top of the script.

## Contributing

```bash
pip install -r requirements-dev.txt
make lint      # check before committing
make test      # run the full test suite
```

CI runs lint and tests on every pull request to `main`. Branch protection (require passing CI, require PR review) is a manual GitHub setting on the repository.
