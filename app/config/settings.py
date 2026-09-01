# ============================================================
# CONFIGURATION CENTRALISÉE — FORMA-IA config/settings.py
# ============================================================

import os
from dotenv import load_dotenv

load_dotenv()


class Settings:
    """Configuration unique pour tout le projet"""

    # ========================================================
    # OPENROUTER
    # ========================================================
    OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

    # Modèle gratuit par défaut
    OPENROUTER_MODEL = os.getenv(
        "OPENROUTER_MODEL",
        "openrouter/free"
    )

    # ========================================================
    # TAVILY
    # ========================================================
    TAVILY_API_KEY = os.getenv("TAVILY_API_KEY")

    # ========================================================
    # BASE DE DONNÉES
    # ========================================================
    DATABASE_URL = os.getenv(
        "DATABASE_URL",
        "postgresql://postgres:admin123@127.0.0.1:5432/formaia"
    )

    # ========================================================
    # ENVIRONNEMENT
    # ========================================================
    ENVIRONMENT = os.getenv(
        "ENVIRONMENT",
        "development"
    )

    DEBUG = os.getenv(
        "DEBUG",
        "True"
    ).lower() == "true"

    # ========================================================
    # LOGGING
    # ========================================================
    LOG_LEVEL = os.getenv(
        "LOG_LEVEL",
        "INFO"
    ).upper()

    # ========================================================
    # CORS
    # ========================================================
    CORS_ORIGINS = os.getenv(
        "CORS_ORIGINS",
        "http://localhost:3000,http://localhost:8501,http://localhost:8000"
    )

    # ========================================================
    # VALIDATION
    # ========================================================
    @classmethod
    def validate(cls):
        """Vérifie que les clés nécessaires sont présentes"""

        if not cls.OPENROUTER_API_KEY:
            raise ValueError(
                "❌ OPENROUTER_API_KEY non trouvée dans .env"
            )

        if not cls.TAVILY_API_KEY:
            raise ValueError(
                "❌ TAVILY_API_KEY non trouvée dans .env"
            )

        return True


settings = Settings()
