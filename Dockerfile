# Use the builder image to install dependencies and fontconfig
FROM python:3.10-slim AS builder

WORKDIR /app

# Install Poppler utilities and clean up in one layer to reduce image size
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    poppler-utils \
    fontconfig \
    libfreetype6-dev \
    libfribidi-dev \
    libharfbuzz-dev \
    libpng-dev \
    libjpeg-dev \
    build-essential && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Copy requirements files first to leverage Docker cache
COPY requirements.txt requirements-base.txt ./
RUN pip3 install --no-cache-dir -r requirements.txt

# Start the final stage of the build
FROM python:3.10-slim

# Install fontconfig in the final image
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

# Copy installed dependencies from the builder
COPY --from=builder /usr/local/lib/python3.10/site-packages /usr/local/lib/python3.10/site-packages
COPY --from=builder /usr/bin/pdftotext /usr/bin/pdftotext
COPY --from=builder /usr/bin/pdfinfo /usr/bin/pdfinfo
COPY --from=builder /usr/share/fontconfig /usr/share/fontconfig
COPY --from=builder /usr/share/fonts /usr/share/fonts

# Copy the necessary font files
COPY fonts/helvetica.ttf /usr/share/fonts/custom/
COPY fonts/helvetica-bold.ttf /usr/share/fonts/custom/
COPY fonts/Bahnschrift.ttf /usr/share/fonts/custom/

# Update the font cache
RUN fc-cache -fv

WORKDIR /app

# Copy the application source code
COPY . .

# Set environment variables
ENV PYTHONPATH=/app \
    HOST=0.0.0.0 \
    PORT=5005

# The port number the container should expose
EXPOSE 5005

# this is where the sqlite database should be mounted
VOLUME /app/data

ENV CHURCHTOOLS_BASE=evkila.church.tools \
    DB_PATH=/app/data/evkila.db

CMD [ "python3", "run_fastapi.py"]
