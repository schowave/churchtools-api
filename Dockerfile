FROM python:3.14-slim AS builder

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
RUN pip3 install --no-cache-dir -r requirements.txt

# Final stage
FROM python:3.14-slim

# Install runtime dependencies only
RUN apt-get update && \
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

# Copy Python packages and scripts from builder
COPY --from=builder /usr/local/lib/python3.14/site-packages /usr/local/lib/python3.14/site-packages
COPY --from=builder /usr/local/bin/ /usr/local/bin/

# pip is not needed at runtime; removing it drops its vendored dependencies from the image
RUN python -m pip uninstall -y pip

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
