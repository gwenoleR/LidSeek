FROM python:3.11-slim

WORKDIR /app

COPY app/ /app/
COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

# Create the download folder
RUN mkdir -p /downloads

EXPOSE 8081


# Ajout du dossier /app au PYTHONPATH pour corriger les imports en mode dev
ENV PYTHONPATH=/app
ENV FLASK_ENV=development

# Utiliser le module app.main comme point d'entrée Flask
ENV FLASK_APP=app.main

CMD ["flask", "--app=app.main", "--debug", "run", "--host=0.0.0.0", "--port=8081"]
