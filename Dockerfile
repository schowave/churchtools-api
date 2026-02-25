FROM python:3.12-slim AS builder

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
FROM python:3.12-slim

# Install runtime dependencies only
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    poppler-utils \
    fontconfig \
    libfreetype6 \
    libfribidi0 \
    libharfbuzz0b \
    libpng16-16 \
    libjpeg62-turbo && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Copy Python packages and scripts from builder
COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin/ /usr/local/bin/

# Copy custom fonts and rebuild font cache
COPY fonts/ /usr/share/fonts/custom/
RUN fc-cache -fv

WORKDIR /app

# Copy application source and fonts
COPY app/ ./app/
COPY fonts/ ./fonts/
COPY run_fastapi.py ./

ARG APP_VERSION=0.0.0
ENV PYTHONPATH=/app \
    APP_VERSION=${APP_VERSION} \
    CHURCHTOOLS_BASE=evkila.church.tools \
    DB_PATH=/app/data/evkila.db

EXPOSE 5005
VOLUME /app/data

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "5005"]
