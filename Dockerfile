FROM amd64/python:3.12-slim

# Install Poppler utilities
RUN apt-get update && \
    apt-get install -y poppler-utils fontconfig && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

RUN mkdir -p /usr/share/fonts/custom

# Copy Helvetica font files into the container
COPY fonts/helvetica.ttf /usr/share/fonts/custom/
COPY fonts/helvetica-bold.ttf /usr/share/fonts/custom/

# Update the font cache
RUN fc-cache -fv

WORKDIR /app

COPY requirements.txt requirements.txt
RUN pip3 install -r requirements.txt

COPY . .

# Set environment variables
ENV FLASK_APP run.py
ENV FLASK_RUN_HOST 0.0.0.0

# The port number the container should expose
EXPOSE 5000


CMD [ "python3", "-m" , "flask", "run"]
