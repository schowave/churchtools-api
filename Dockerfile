FROM python:3.15-slim AS builder

WORKDIR /app

# Install build dependencies for Python packages with C extensions
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    libfreetype6-dev \
    libfribidi-dev \
    libharfbuzz-dev \
    libpng-dev \
    libjpeg-dev \
    build-essential && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
# Isolated venv: the runtime stage copies only /opt/venv, independent of the Python minor
# version and without builder leftovers under /usr/local. pip is dropped, it is not needed at runtime.
RUN python -m venv /opt/venv && \
    /opt/venv/bin/pip install --no-cache-dir -r requirements.txt && \
    /opt/venv/bin/pip uninstall -y pip

# Final stage
FROM python:3.15-slim

# Install runtime dependencies only. The upgrade pulls Debian security fixes
# that the python base image has not been rebuilt with yet (the CI image scan fails otherwise).
RUN apt-get update && \
    apt-get upgrade -y && \
    apt-get install -y --no-install-recommends \
    poppler-utils \
    fontconfig \
    libfreetype6 \
    libfribidi0 \
    libharfbuzz0b \
    libpng16-16 \
    libjpeg62-turbo \
    sqlite3 && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Python packages and their scripts (uvicorn, alembic) from the builder venv
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# pip is not needed at runtime; removing it drops its vendored dependencies from the image
RUN /usr/local/bin/python -m pip uninstall -y pip

# Copy custom fonts and rebuild font cache
COPY app/resources/fonts/ /usr/share/fonts/custom/
RUN fc-cache -fv

# Unprivileged user the app runs as (entrypoint.sh drops root after fixing volume ownership)
RUN groupadd --system app && useradd --system --gid app --no-create-home app

WORKDIR /app

# Copy application source (including fonts), config and migrations
COPY app/ ./app/
COPY alembic/ ./alembic/
COPY alembic.ini ./
COPY entrypoint.sh ./
RUN chmod +x entrypoint.sh
COPY pyproject.toml ./

# entrypoint.sh handles:
# 1. DB directory creation
# 2. Alembic stamp for existing DBs without migration tracking
# 3. Alembic upgrade head (run migrations)
# 4. Start uvicorn

ENV PYTHONPATH=/app \
    DB_PATH=/app/data/churchtools.db

EXPOSE 5005
VOLUME /app/data

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:5005/health')" || exit 1

ENTRYPOINT ["./entrypoint.sh"]
