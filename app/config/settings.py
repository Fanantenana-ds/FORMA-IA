# app/config/settings.py
from typing import Optional

from dotenv import load_dotenv
from pydantic_settings import BaseSettings

load_dotenv()

class Settings(BaseSettings):
    """Configuration unique pour tout le projet avec Pydantic"""
    
    # ========================================================
    # BASE DE DONNÉES
    # ========================================================
    DATABASE_URL: str = "postgresql://postgres:admin123@127.0.0.1:5432/formaia"
    
    # ========================================================
    # SÉCURITÉ
    # ========================================================
    SECRET_KEY: str = "votre_secret_key_aleatoire_longue_et_complexe"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 480  # 8h en dev (surcharger via .env en prod)
    
    # ========================================================
    # GROQ (ta config principale)
    # ========================================================
    GROQ_API_KEY: Optional[str] = None
    GROQ_MODEL: str = "openai/gpt-oss-20b"
    GROQ_TIMEOUT: int = 20
    GROQ_MAX_OUTPUT_TOKENS: int = 1200
    
    # ========================================================
    # TAVILY
    # ========================================================
    TAVILY_API_KEY: Optional[str] = None
    TAVILY_MAX_RESULTS: int = 10
    TAVILY_TIMEOUT: int = 10
    
    # ========================================================
    # ENVIRONNEMENT
    # ========================================================
    ENVIRONMENT: str = "development"
    DEBUG: bool = True
    LOG_LEVEL: str = "INFO"
    LOG_FORMAT: str = "text"
    
    # ========================================================
    # CORS
    # ========================================================
    CORS_ORIGINS: str = "http://localhost:3000,http://localhost:8501,http://localhost:8000"
    
    # ========================================================
    # LIMITES
    # ========================================================
    MAX_PROMPT_CHARS: int = 18000
    MAX_SOURCE_CHARS_TOTAL: int = 4500
    MAX_SOURCE_CHARS_EACH: int = 1000
    RATE_LIMIT_PER_MINUTE: int = 100
    
    # ========================================================
    # RAG
    # ========================================================
    EMBEDDING_MODEL: str = "all-MiniLM-L6-v2"
    RAG_TOP_K: int = 5
    RAG_CHUNK_SIZE: int = 500
    RAG_CHUNK_OVERLAP: int = 50
    
    # ========================================================
    # EMAIL SMTP (accusé de réception candidats)
    # ========================================================
    SMTP_HOST: str = ""
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_FROM: str = ""

    # ========================================================
    # EMAIL IMAP (lecture candidatures reçues par email)
    # ========================================================
    IMAP_HOST: str = ""
    IMAP_PORT: int = 993
    IMAP_USER: str = ""
    IMAP_PASSWORD: str = ""
    RH_EMAIL_POSTE_DEFAUT: str = "formateur-ia"

    # ========================================================
    # SCHEDULER EMAIL M4 (lecture IMAP automatique)
    # ========================================================
    RH_EMAIL_AUTO_ENABLED: bool = False
    RH_EMAIL_CHECK_INTERVAL_MINUTES: int = 30

    # ========================================================
    # Pydantic Configuration
    # ========================================================
    class Config:
        # ⚠️ IGNORE toutes les variables supplémentaires dans .env
        extra = "ignore"
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False  # Permet d'ignorer la casse

settings = Settings()