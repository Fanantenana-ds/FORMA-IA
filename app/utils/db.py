# ============================================================
# FORMA-IA - app/utils/db.py
# Connexion PostgreSQL (Windows)
# ============================================================

import os
import logging

from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.orm import declarative_base, sessionmaker

# ============================================================
# Chargement des variables d'environnement
# ============================================================

load_dotenv()

logger = logging.getLogger(__name__)

# ============================================================
# Configuration
# ============================================================

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://postgres:admin123@127.0.0.1:5432/formaia"
)

logger.info("📊 Connexion à PostgreSQL")

# ============================================================
# Engine SQLAlchemy
# ============================================================

engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    pool_recycle=300,
    echo=False,
)

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)

Base = declarative_base()

# ============================================================
# Sessions
# ============================================================

def get_db():
    db = SessionLocal()
    try:
        yield db
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def get_db_session():
    return SessionLocal()


# ============================================================
# Test connexion
# ============================================================

def test_connection():
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))

        logger.info("✅ Connexion PostgreSQL réussie")
        return True

    except Exception as e:
        logger.exception("Erreur PostgreSQL")
        logger.error(e)
        return False


# ============================================================
# Création des tables
# ============================================================

def init_db():
    try:
        logger.info("📦 Création des tables...")

        Base.metadata.create_all(bind=engine)

        logger.info("✅ Tables créées avec succès")

        return True

    except Exception as e:

        logger.exception("Erreur création tables")
        logger.error(e)

        return False


# ============================================================
# Vérifie si la base existe
# ============================================================

def database_exists():

    try:

        with engine.connect() as conn:

            conn.execute(text("SELECT 1"))

        return True

    except Exception:

        return False


# ============================================================
# Création base (inutile si déjà créée)
# ============================================================

def create_database_if_not_exists():

    logger.info("✅ Base 'formaia' déjà existante")

    return True


# ============================================================
# Suppression des tables
# ============================================================

def drop_db():

    Base.metadata.drop_all(bind=engine)

    logger.warning("Toutes les tables ont été supprimées")