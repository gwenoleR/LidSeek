FROM python:3.11-slim

WORKDIR /app

COPY app/ /app/
COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

# Create the download folder
RUN mkdir -p /downloads

EXPOSE 8081

ENV FLASK_ENV=development
ENV FLASK_APP=main.py

CMD ["flask", "--app=main", "--debug", "run", "--host=0.0.0.0", "--port=8081"]
