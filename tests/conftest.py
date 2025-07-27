import pytest
from app.main import create_app
from app.database import Database
import os
import tempfile
import fakeredis

@pytest.fixture
def redis_client():
    return fakeredis.FakeStrictRedis()

@pytest.fixture
def app(redis_client):
    # Création d'une base de données temporaire pour les tests
    db_fd, db_path = tempfile.mkstemp()
    app = create_app()
    app.config.update({
        'TESTING': True,
        'DATABASE': db_path,
    })
    
    # Injection du client Redis de test
    app.redis_client = redis_client

    yield app

    # Nettoyage après les tests
    os.close(db_fd)
    os.unlink(db_path)

@pytest.fixture
def client(app):
    return app.test_client()

@pytest.fixture
def runner(app):
    return app.test_cli_runner()

@pytest.fixture(autouse=True)
def test_database():
    """Fixture qui crée une nouvelle base de données en mémoire pour chaque test."""
    # Assure qu'aucune connexion précédente n'est active
    Database.close_memory_connection()
    
    # Crée une nouvelle instance de base de données
    db = Database(":memory:")
    
    # Renvoie la base de données pour le test
    yield db
    
    # Nettoie et ferme la base de données après le test
    try:
        db.cleanup()
    finally:
        Database.close_memory_connection()

@pytest.fixture(autouse=True)
def setup_database(test_database):
    """Fixture qui réinitialise la base de données avant chaque test."""
    # Cette fixture ne fait rien directement car test_database gère déjà tout,
    # mais elle garantit que test_database est exécuté avant chaque test
    yield