# ============================================================
# FORMA-IA — MAIN.PY (Point d'entrée FastAPI)
# ============================================================
# Version : V1.0
# Date : Aout 2026
# ============================================================

import os
import logging
import time
from datetime import datetime
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from dotenv import load_dotenv

# ============================================================
# 1. CHARGEMENT DES VARIABLES D'ENVIRONNEMENT
# ============================================================
load_dotenv()

# ============================================================
# 2. CONFIGURATION DU LOGGING
# ============================================================
logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# ============================================================
# 3. CRÉATION DE L'APPLICATION FASTAPI
# ============================================================
app = FastAPI(
    title="FORMA-IA API",
    description="""
    Plateforme intelligente de gestion de la formation pour ALTIORA.

    ## Modules disponibles :
    - **M1** : Veille Marché Intelligente
    - **M2** : Génération de TDR
    - **M5** : Gestion des Formations
    - **M6** : Attestations de Formation
    - **M8** : Dashboard Statistique

    ## Technologies :
    - FastAPI
    - Claude API (Anthropic)
    - Tavily API
    - PostgreSQL
    - LangGraph
    """,
    version="1.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
    contact={
        "name": "ALTIORA",
        "url": "https://altiora-prest.com",
        "email": "contact@altiora-prest.com"
    },
    license_info={
        "name": "Propriétaire - ALTIORA",
    }
)

# ============================================================
# 4. CONFIGURATION CORS
# ============================================================
origins = os.getenv("CORS_ORIGINS", "http://localhost:3000,http://localhost:8501,http://localhost:8000")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in origins.split(",")],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============================================================
# 5. MIDDLEWARE PERSONNALISÉ (Logging)
# ============================================================

class LoggingMiddleware(BaseHTTPMiddleware):
    """Middleware pour logger toutes les requêtes"""

    async def dispatch(self, request: Request, call_next):
        start_time = time.time()

        # Logger la requête
        logger.info(f"Requête: {request.method} {request.url.path}")

        # Traiter la requête
        response = await call_next(request)

        # Logger la réponse
        process_time = time.time() - start_time
        logger.info(
            f"Réponse: {request.method} {request.url.path} "
            f"- Status: {response.status_code} "
            f"- Temps: {process_time:.3f}s"
        )

        # Ajouter l'en-tête de temps de réponse
        response.headers["X-Process-Time"] = str(process_time)
        return response

# Ajouter le middleware de logging
app.add_middleware(LoggingMiddleware)

# ============================================================
# 6. ROUTES DE BASE
# ============================================================

@app.get("/")
async def root():
    """Point d'entrée principal de l'API"""
    return {
        "message": "🚀 FORMA-IA API est en ligne !",
        "version": "1.0.0",
        "status": "operational",
        "environment": os.getenv("ENVIRONMENT", "development"),
        "docs": "/api/docs",
        "redoc": "/api/redoc",
        "timestamp": datetime.now().isoformat()
    }

@app.get("/health")
async def health_check():
    """Vérification de l'état de santé de l'API"""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "environment": os.getenv("ENVIRONMENT", "development"),
        "version": "1.0.0"
    }

@app.get("/api/version")
async def get_version():
    """Retourne la version de l'API"""
    return {
        "version": "1.0.0",
        "environment": os.getenv("ENVIRONMENT", "development"),
        "build_date": "2026-08-01"
    }

@app.get("/api/status")
async def get_status():
    """Statut détaillé de l'API"""
    return {
        "status": "operational",
        "timestamp": datetime.now().isoformat(),
        "modules": {
            "m1_veille": "not_loaded",
            "m2_tdr": "not_loaded",
            "m5_formation": "not_loaded",
            "m6_attestation": "not_loaded",
            "m8_dashboard": "not_loaded"
        },
        "database": "checking",
        "cache": "checking"
    }

# ============================================================
# 7. GESTION DES ERREURS
# ============================================================

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Gestionnaire global des exceptions"""
    logger.error(f"Erreur sur {request.url.path}: {str(exc)}")
    return JSONResponse(
        status_code=500,
        content={
            "success": False,
            "error": str(exc),
            "path": request.url.path,
            "timestamp": datetime.now().isoformat()
        }
    )

@app.exception_handler(404)
async def not_found_handler(request: Request, exc):
    """Gestionnaire des routes non trouvées"""
    return JSONResponse(
        status_code=404,
        content={
            "success": False,
            "error": "Route non trouvée",
            "path": request.url.path,
            "timestamp": datetime.now().isoformat()
        }
    )

@app.exception_handler(405)
async def method_not_allowed_handler(request: Request, exc):
    """Gestionnaire des méthodes non autorisées"""
    return JSONResponse(
        status_code=405,
        content={
            "success": False,
            "error": "Méthode non autorisée",
            "path": request.url.path,
            "method": request.method,
            "timestamp": datetime.now().isoformat()
        }
    )
# ============================================================
# 8. IMPORT ET ENREGISTREMENT DES ROUTES IA (MODULES)
# ============================================================

# Importer les routes M1
from app.api.v1.routes_veille import router as veille_router
app.include_router(veille_router, prefix="/api/v1")
logger.info("✅ Module M1 (Veille) chargé")

# Les autres modules seront ajoutés plus tard
# from app.api.v1.routes_tdr import router as tdr_router
# app.include_router(tdr_router, prefix="/api/v1")

# from app.api.v1.routes_formation import router as formation_router
# app.include_router(formation_router, prefix="/api/v1")

# from app.api.v1.routes_attestation import router as attestation_router
# app.include_router(attestation_router, prefix="/api/v1")

# from app.api.v1.routes_dashboard import router as dashboard_router
# app.include_router(dashboard_router, prefix="/api/v1")

# ============================================================
# 9. ÉVÉNEMENTS DE DÉMARRAGE ET D'ARRÊT
# ============================================================

@app.on_event("startup")
async def startup_event():
    """Actions à effectuer au démarrage de l'application"""
    logger.info("🚀 FORMA-IA API démarrage...")
    logger.info(f"📌 Environnement: {os.getenv('ENVIRONMENT', 'development')}")
    logger.info(f"📌 Modèle utilisé: Groq (llama3-70b-8192)")

    # ... (le reste du code existant)

    # --- Vérification des clés API ---
    groq_key = os.getenv("GROQ_API_KEY")
    if groq_key and groq_key != "gsk_...":
        logger.info(f"✅ Clé Groq présente: {groq_key[:10]}...")
    else:
        logger.warning("⚠️ Clé Groq manquante ou invalide dans .env")

    # --- Tavily ---
    tavily_key = os.getenv("TAVILY_API_KEY")
    if tavily_key and tavily_key != "tvly-...":
        logger.info(f"✅ Clé Tavily présente: {tavily_key[:10]}...")
    else:
        logger.warning("⚠️ Clé Tavily manquante ou invalide dans .env")

    logger.info("✅ API prête à recevoir des requêtes")
    logger.info(f"📌 Documentation: http://localhost:8000/api/docs")


# ============================================================
# 9. ÉVÉNEMENTS DE DÉMARRAGE ET D'ARRÊT
# # ============================================================

# @app.on_event("startup")
# async def startup_event():
#     """Actions à effectuer au démarrage de l'application"""
#     logger.info("🚀 FORMA-IA API démarrage...")
#     logger.info(f"📌 Environnement: {os.getenv('ENVIRONMENT', 'development')}")
#     logger.info(f"📌 Modèle Claude: {os.getenv('CLAUDE_MODEL', 'claude-3-5-sonnet-20241022')}")
    
#     # --- Vérification de la base de données ---
#     try:
#         from app.utils.db import test_connection, init_db, create_database_if_not_exists
        
#         # Créer la base si elle n'existe pas
#         create_database_if_not_exists()
        
#         # Tester la connexion
#         if test_connection():
#             logger.info("✅ Connexion à PostgreSQL établie")
#             # Créer les tables si elles n'existent pas
#             init_db()
#         else:
#             logger.warning("⚠️ PostgreSQL n'est pas accessible")
#             logger.warning("   💡 Assure-toi que PostgreSQL est installé et en cours d'exécution")
#             logger.warning("   💡 Vérifie les identifiants dans .env (DATABASE_URL)")
#     except ImportError as e:
#         logger.warning(f"⚠️ Module db non trouvé: {e}")
#     except Exception as e:
#         logger.warning(f"⚠️ Erreur PostgreSQL: {e}")

#     # --- Vérification des clés API ---
#     anthropic_key = os.getenv("ANTHROPIC_API_KEY")
#     if anthropic_key and anthropic_key != "sk-ant-votre-clef-ici":
#         logger.info(f"✅ Clé Anthropic présente: {anthropic_key[:10]}...")
#     else:
#         logger.warning("⚠️ Clé Anthropic manquante ou invalide dans .env")

#     tavily_key = os.getenv("TAVILY_API_KEY")
#     if tavily_key and tavily_key != "tvly-votre-clef-ici":
#         logger.info(f"✅ Clé Tavily présente: {tavily_key[:10]}...")
#     else:
#         logger.warning("⚠️ Clé Tavily manquante ou invalide dans .env")

#     logger.info("✅ API prête à recevoir des requêtes")
#     logger.info(f"📌 Documentation: http://localhost:8000/api/docs")

# @app.on_event("shutdown")
# async def shutdown_event():
#     """Actions à effectuer à l'arrêt de l'application"""
#     logger.info("🛑 FORMA-IA API arrêt...")

# ============================================================
# 10. POINT D'ENTRÉE POUR L'EXÉCUTION DIRECTE
# ============================================================

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host="127.0.0.1",  # localhost
        port=8000,
        reload=True,
        log_level="info"
    )