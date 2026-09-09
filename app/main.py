from datetime import datetime
import logging
import time

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware

from app.config.settings import settings
from app.database import Base, engine

# Modèles (tsy miova)
from app.models.user import User
from app.models.revoked_token import RevokedToken
from app.models.opportunite import Opportunite
from app.models.historique_analyse import HistoriqueAnalyse

# Routers IA (M1, M2)
from app.api.v1.routes_veille import router as veille_router
from app.api.v1.routes_tdr import router as tdr_router

# Router Backend (auth, CRUD, analyse, document, formation)
from app.api.v1.router import api_router


# ============================================================
# DATABASE
# ============================================================
Base.metadata.create_all(bind=engine)


# ============================================================
# LOGGING
# ============================================================
logging.basicConfig(
    level=settings.LOG_LEVEL,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


# ============================================================
# APPLICATION
# ============================================================
app = FastAPI(
    title="FORMA-IA API",
    description="Plateforme intelligente de gestion de la formation pour ALTIORA.",
    version="1.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
    openapi_tags=[
        {
            "name": "Système",
            "description": "Endpoints système (santé, version)"
        },
        {
            "name": "M1 - Veille Marché",
            "description": "Analyse d'opportunités (recherche Tavily + analyse Groq)"
        },
        {
            "name": "M2 - TDR",
            "description": "Génération de Termes de Référence pour formations"
        },
        {
            "name": "Authentification",
            "description": "Inscription, connexion, JWT, déconnexion"
        },
        {
            "name": "Opportunités",
            "description": "CRUD complet des opportunités détectées"
        },
        {
            "name": "Analyse",
            "description": "Analyse IA des opportunités (avec Groq)"
        },
        {
            "name": "Documents",
            "description": "Génération et validation des documents (TDR)"
        },
        {
            "name": "Formations",
            "description": "Gestion des sessions, séances, présences et participants"
        }
    ]
)


# ============================================================
# CORS
# ============================================================
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        origin.strip()
        for origin in settings.CORS_ORIGINS.split(",")
        if origin.strip()
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================
# LOGGING MIDDLEWARE
# ============================================================
class LoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        start_time = time.time()
        logger.info("Requête: %s %s", request.method, request.url.path)
        response = await call_next(request)
        process_time = time.time() - start_time
        response.headers["X-Process-Time"] = f"{process_time:.3f}"
        logger.info(
            "Réponse: %s %s - Status: %s - Temps: %.3fs",
            request.method, request.url.path,
            response.status_code, process_time
        )
        return response

app.add_middleware(LoggingMiddleware)


# ============================================================
# ROUTES SYSTÈME
# ============================================================
@app.get("/", tags=["Système"])
async def root():
    return {
        "message": "FORMA-IA API est en ligne !",
        "version": "1.0.0",
        "docs": "/api/docs",
    }

@app.get("/health", tags=["Système"])
async def health_check():
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
    }


# ============================================================
# ROUTES MÉTIER
# ============================================================

# --- M1: Veille Marché ---
app.include_router(veille_router, prefix="/api/v1")
logger.info("✅ Module M1 (Veille) chargé")

# --- M2: TDR ---
app.include_router(tdr_router, prefix="/api/v1")
logger.info("✅ Module M2 (TDR) chargé")

# --- Backend (auth, opportunités, analyse, documents, formations) ---
app.include_router(api_router, prefix="/api/v1")
logger.info("✅ Routes Backend chargées")


# ============================================================
# STARTUP
# ============================================================
@app.on_event("startup")
async def startup():
    logger.info("🚀 FORMA-IA API démarrage...")
    logger.info("📌 Environnement: %s", settings.ENVIRONMENT)
    logger.info("🤖 Modèle Groq: %s", settings.GROQ_MODEL)