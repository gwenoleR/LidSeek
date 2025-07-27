FROM python:3.11-slim

WORKDIR /usr/src/app

# Copier les fichiers nécessaires pour l'installation
COPY setup.py .
COPY requirements.txt .
COPY app app/

# Installer les dépendances et le package en mode éditable
RUN pip install --no-cache-dir -r requirements.txt && \
    pip install -e .

# Créer le dossier de téléchargement
RUN mkdir -p /downloads

EXPOSE 8081

ENV PYTHONPATH=/usr/src/app
ENV FLASK_APP=app.main:create_app
ENV FLASK_ENV=development

CMD ["python", "-m", "flask", "run", "--host=0.0.0.0", "--port=8081"]
