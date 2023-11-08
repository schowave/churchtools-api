FROM amd64/python:3.12-slim

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
