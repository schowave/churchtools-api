FROM amd64/python:3.12-slim

WORKDIR /app

COPY requirements.txt requirements.txt
RUN pip3 install -r requirements.txt

COPY . .

ENV FLASK_APP app.py

CMD [ "python3", "-m" , "flask", "run", "--host=0.0.0.0"]
