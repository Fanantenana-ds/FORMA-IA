"""
=============================================================================
FORMA-IA — APPLICATION PRINCIPALE
=============================================================================
Plateforme intelligente de gestion de la formation pour ALTIORA PREST.
=============================================================================
"""

import os
import time
import logging
from datetime import datetime

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware

from app.config.settings import settings
from app.database import Base, engine

# ─────────────────────────────────────────────────────────────
# MODÈLES
# ─────────────────────────────────────────────────────────────
from app.models.user import User
from app.models.revoked_token import RevokedToken
from app.models.opportunite import Opportunite
from app.models.historique_analyse import HistoriqueAnalyse

# ─────────────────────────────────────────────────────────────
# ROUTERS
# ─────────────────────────────────────────────────────────────
from app.api.v1.routes_veille import (
    router as veille_router,
    orchestrator as veille_orchestrator,
)
from app.api.v1.routes_tdr import router as tdr_router
from app.api.v1.router import api_router
from app.services.veille import auto_detection_service
from app.services import ia_health


# =============================================================================
# CONFIG — VERBOSE
# =============================================================================
# VERBOSE_LOGS=true      → logs détaillés (défaut : true en dev)
# VERBOSE_HTTP=true      → logs de chaque requête HTTP (défaut : true en dev)
# VERBOSE_SKIP_HEALTH=true → ignore /health, /api/docs dans les logs HTTP
VERBOSE_LOGS = os.getenv("VERBOSE_LOGS", "true").lower() == "true"
VERBOSE_HTTP = os.getenv("VERBOSE_HTTP", "true").lower() == "true"
VERBOSE_SKIP_HEALTH = os.getenv("VERBOSE_SKIP_HEALTH", "true").lower() == "true"


def vlog(msg: str, level: str = "info") -> None:
    """Log conditionnel (VERBOSE_LOGS)."""
    if VERBOSE_LOGS:
        getattr(logging.getLogger("app.main"), level)(msg)


# =============================================================================
# DATABASE
# =============================================================================
Base.metadata.create_all(bind=engine)


# =============================================================================
# LOGGING
# =============================================================================
logging.basicConfig(
    level=settings.LOG_LEVEL,
    format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


# =============================================================================
# APPLICATION FASTAPI
# =============================================================================
app = FastAPI(
    title="FORMA-IA API",
    description="Plateforme intelligente de gestion de la formation pour ALTIORA PREST.",
    version="1.1.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
    openapi_tags=[
        {"name": "Système",           "description": "Endpoints système (santé, version)"},
        {"name": "M1 - Veille Marché","description": "Analyse d'opportunités (avec IA)"},
        {"name": "M2 - TDR",          "description": "Génération de Termes de Référence"},
        {"name": "M3 — IA Offres",    "description": "Génération d'offres technique + financière"},
        {"name": "Préparation — IA",  "description": "Budget prévisionnel + Emploi du temps"},
        {"name": "M5 — IA Formations","description": "6 agents : forms, niveaux, satisfaction, présences, attestations, rapport"},
        {"name": "M7 — IA Facturation","description": "Relances de facture (niveaux 1/2/3)"},
        {"name": "Authentification",  "description": "Inscription, connexion, JWT, déconnexion"},
        {"name": "Opportunités",      "description": "CRUD complet des opportunités détectées"},
        {"name": "Documents",         "description": "Génération et validation des documents (TDR)"},
        {"name": "Formations",        "description": "Gestion des sessions, séances, présences et participants"},
        {"name": "Facturation",       "description": "Émission de factures, paiements, relances"},
        {"name": "Dashboard",         "description": "Statistiques et indicateurs"},
    ],
)


# =============================================================================
# CORS
# =============================================================================
_cors_origins = [
    origin.strip()
    for origin in settings.CORS_ORIGINS.split(",")
    if origin.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

if VERBOSE_LOGS:
    logger.info("🌐 CORS configuré — %d origine(s) autorisée(s)", len(_cors_origins))


# =============================================================================
# MIDDLEWARE — LOGGING HTTP
# =============================================================================
# Chemins à ignorer dans les logs HTTP (si VERBOSE_SKIP_HEALTH=true)
_SKIP_PATHS = (
    "/health",
    "/api/docs",
    "/api/redoc",
    "/api/openapi.json",
    "/favicon.ico",
)


class LoggingMiddleware(BaseHTTPMiddleware):
    """Middleware HTTP avec logs verbeux et time tracking."""

    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        method = request.method

        # Skip les endpoints techniques
        if VERBOSE_SKIP_HEALTH and any(path.startswith(p) for p in _SKIP_PATHS):
            return await call_next(request)

        if not VERBOSE_HTTP:
            return await call_next(request)

        start_time = time.perf_counter()
        client_ip = request.client.host if request.client else "unknown"

        vlog(f"➡️  {method:6s} {path} — client={client_ip}")

        try:
            response = await call_next(request)
        except Exception as exc:
            elapsed = round(time.perf_counter() - start_time, 3)
            logger.exception(
                "💥 %s %s — ERREUR après %.3fs : %s",
                method, path, elapsed, exc,
            )
            raise

        process_time = time.perf_counter() - start_time
        response.headers["X-Process-Time"] = f"{process_time:.3f}"

        # Emoji selon status
        if response.status_code < 300:
            icon = "✅"
        elif response.status_code < 400:
            icon = "↪️"
        elif response.status_code < 500:
            icon = "⚠️"
        else:
            icon = "❌"

        vlog(
            f"{icon} {method:6s} {path} — {response.status_code} "
            f"({process_time*1000:.0f}ms)"
        )

        return response


app.add_middleware(LoggingMiddleware)


# =============================================================================
# ROUTES SYSTÈME
# =============================================================================
@app.get("/", tags=["Système"])
async def root():
    return {
        "message": "FORMA-IA API est en ligne !",
        "version": "1.1.0",
        "docs": "/api/docs",
    }


@app.get("/health", tags=["Système"])
async def health_check():
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
    }


@app.get("/health/ia", tags=["Système"])
async def health_ia():
    """
    État des modules IA (M1, M2, M3, Préparation, M5, M6, M7).
    'degraded' si un agent requis n'a pas pu être chargé ; répond toujours HTTP 200.
    """
    return {**ia_health.collecter(), "timestamp": datetime.now().isoformat()}


# =============================================================================
# ROUTES MÉTIER
# =============================================================================

# --- M1 : Veille Marché ---
app.include_router(veille_router, prefix="/api/v1")
logger.info("✅ M1 — Veille marché chargé")

# --- M2 : TDR ---
app.include_router(tdr_router, prefix="/api/v1")
logger.info("✅ M2 — TDR chargé")

# --- Backend + IA (M3, Préparation, M5, M7, Auth, CRUD, ...) ---
app.include_router(api_router, prefix="/api/v1")
logger.info("✅ Backend + IA chargés (auth, CRUD, M3, Préparation, M5, M7)")


# =============================================================================
# BILAN DES ROUTES AU DÉMARRAGE
# =============================================================================
def _log_routes_summary() -> None:
    """Log un résumé des routes chargées, groupées par tag."""
    if not VERBOSE_LOGS:
        return

    routes = [
        r for r in app.routes
        if hasattr(r, "methods") and getattr(r, "path", "").startswith("/")
    ]

    # Grouper par tag
    by_tag: dict = {}
    for r in routes:
        tags = getattr(r, "tags", []) or ["(sans tag)"]
        for tag in tags:
            by_tag.setdefault(tag, []).append(r)

    total = len(routes)
    logger.info("=" * 70)
    logger.info(f"📊 BILAN ROUTES — {total} endpoint(s) chargé(s)")
    for tag, tag_routes in sorted(by_tag.items()):
        logger.info(f"   🏷️  {tag} : {len(tag_routes)} route(s)")
    logger.info("=" * 70)


# =============================================================================
# STARTUP
# =============================================================================
@app.on_event("startup")
async def startup():
    logger.info("=" * 70)
    logger.info("🚀 FORMA-IA API — DÉMARRAGE")
    logger.info("=" * 70)
    logger.info(f"   📌 Environnement  : {settings.ENVIRONMENT}")
    logger.info(f"   🤖 Provider LLM   : Groq (modèle={settings.GROQ_MODEL})")
    logger.info(f"   🔧 Verbose logs   : {VERBOSE_LOGS}")
    logger.info(f"   🔧 Verbose HTTP   : {VERBOSE_HTTP}")
    logger.info(f"   📚 Docs           : /api/docs")
    logger.info(f"   ❤️  Health IA      : /health/ia")
    logger.info("=" * 70)

    # Alerte ERROR si un agent IA requis n'a pas pu être chargé
    ia_health.journaliser_au_demarrage()

    # Bilan des routes
    _log_routes_summary()

    # M1 mode 2 : détection automatique planifiée (inactive sauf VEILLE_AUTO_ENABLED=true)
    auto_detection_service.demarrer_planification(veille_orchestrator)

    logger.info("✅ FORMA-IA API prêt à recevoir des requêtes.")


@app.on_event("shutdown")
async def shutdown():
    logger.info("=" * 70)
    logger.info("🛑 FORMA-IA API — ARRÊT")
    await auto_detection_service.arreter_planification()
    logger.info("✅ Planification arrêtée. Au revoir.")
    logger.info("=" * 70)