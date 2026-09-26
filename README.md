# ChurchTools API

[![Test and Build](https://github.com/schowave/churchtools-api/actions/workflows/test-and-build.yml/badge.svg)](https://github.com/schowave/churchtools-api/actions/workflows/test-and-build.yml)
[![Docker Image](https://img.shields.io/docker/v/schowave/churchtools?sort=semver&label=Docker%20Hub)](https://hub.docker.com/r/schowave/churchtools)
[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![License](https://img.shields.io/github/license/schowave/churchtools-api)](LICENSE)

A web application for creating styled announcement slides from [ChurchTools](https://www.church.tools/) calendar events — exported as PDF or JPEG for use in church services.

<p align="center">
  <img src="images/start.png" alt="Startseite" width="300">
</p>
<p align="center">
  <img src="images/kalenderauswahl.png" alt="Kalenderauswahl" width="300">
</p>
<p align="center">
  <img src="images/termin-folien.png" alt="Termin-Folien" width="300">
</p>

## Features

- **Termin-Folien** — styled announcement slides from calendar appointments, exported as PDF or JPEG (ZIP), with custom colors, logo, and background image
- **Agenda** — service rundowns (songs, items, responsible persons) per event, exportable as PDF
- **Dienstplan** — who serves in which role per event, exportable as PDF per event
- **Calendar selection** — choose one or more public calendars from your ChurchTools instance


## Quick Start

### Docker (recommended)

```bash
docker run -d \
  -e CHURCHTOOLS_BASE=your-instance.church.tools \
  -v ./data:/app/data \
  -p 5005:5005 \
  schowave/churchtools:latest
```

Open [http://localhost:5005](http://localhost:5005)

### From Source

```bash
git clone https://github.com/schowave/churchtools-api.git
cd churchtools-api
cp .env.example .env           # set CHURCHTOOLS_BASE
mise install                   # installs Python + uv, creates .venv
mise run install               # installs app + dev dependencies
mise run run
```

## Configuration

| Variable | Required | Default | Description |
|---|---|---|---|
| `CHURCHTOOLS_BASE` | Yes | — | Your ChurchTools domain (e.g. `my-church.church.tools`) |
| `DB_PATH` | No | `churchtools.db` | Path to the SQLite database file |
| `TIMEZONE` | No | `Europe/Berlin` | Timezone for date display (any valid IANA timezone) |
| `LOG_FORMAT` | No | `console` | Log output format: `console` (human-readable) or `json` |

## Deployment

### Synology NAS

1. Create a project folder on your NAS (e.g. `/volume1/docker/churchtools/`)
2. Add the `docker-compose.yml` from this repository
3. Create a `.env` file with your configuration:

   ```env
   CHURCHTOOLS_BASE=your-instance.church.tools
   ```

4. In **Container Manager** → **Project** → **Create**, point to the folder and start

The included [Watchtower](https://containrrr.dev/watchtower/) service monitors Docker Hub and automatically updates the container when a new release is published.

### Other Platforms

The Docker image `schowave/churchtools` is built for `linux/amd64`. It works on any x86_64 platform that supports Docker or Podman.

```yaml
# docker-compose.yml
services:
  churchtools-api:
    image: schowave/churchtools:latest
    ports:
      - "5005:5005"
    volumes:
      - ./data:/app/data
    environment:
      - CHURCHTOOLS_BASE=your-instance.church.tools
    restart: unless-stopped
```

## Releases

Releases are managed via GitHub Actions:

1. Go to **Actions** → **Release** → **Run workflow**
2. Either enter a version number (e.g. `3.1.0`) or leave empty to auto-increment the patch version (e.g. `3.0.2` → `3.0.3`)
3. The workflow runs tests, updates `pyproject.toml`, creates a git tag, builds the Docker image (linux/amd64), and pushes to Docker Hub
4. Watchtower picks up the new image automatically on connected hosts

> Requires GitHub Secrets: `DOCKERHUB_USERNAME` and `DOCKERHUB_TOKEN`

## Development

Tooling is managed with [mise](https://mise.jdx.dev/) (`mise.toml`): it pins Python and uv and activates `.venv` automatically. Run `mise tasks` for the full list.

| Command | Description |
|---|---|
| `mise run install` | Install app and dev dependencies into `.venv` |
| `mise run run` | Run migrations and start dev server with auto-reload |
| `mise run test` | Run test suite |
| `mise run cov` | Run test suite with coverage report |
| `mise run lint` | Check code style (ruff) |
| `mise run format` | Auto-fix code style |
| `mise run preview` | Render a sample slide PDF to `app/saved_files/preview.pdf` |
| `mise run lock` | Regenerate `requirements.txt` (pinned runtime deps for the Docker image) |
| `mise run build` | Build container image locally (podman) |
| `mise run run-docker` | Build and run the container locally with `./data` as volume |

Local JPEG export needs poppler (`brew install poppler` / `apt install poppler-utils`); the Docker image ships it.

Dependencies are declared in `pyproject.toml`. After changing them, run `mise run lock` so the Docker image picks up the new pins.

CI runs lint and tests on every push to `main` and on pull requests.
