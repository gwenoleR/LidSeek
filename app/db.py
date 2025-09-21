from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import os

# Exemple d'URL PostgreSQL : postgresql+psycopg2://user:password@localhost/dbname
DATABASE_URL = os.getenv('DATABASE_URL', 'postgresql+psycopg2://user:password@localhost/lidseek')

engine = create_engine(DATABASE_URL, echo=False, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)