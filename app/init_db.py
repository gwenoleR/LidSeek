# Pour initialiser la base de données PostgreSQL avec SQLAlchemy ORM
from app.db import engine
from app.models import Base

if __name__ == "__main__":
    Base.metadata.create_all(bind=engine)
    print("Tables créées.")
