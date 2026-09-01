# ============================================================
# FORMA-IA — MAIN.PY
# ============================================================

import logging
import time
from datetime import datetime

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware

from app.config.settings import settings


# ============================================================
# LOGGING
# ============================================================

logging.basicConfig(
    level=settings.LOG_LEVEL,
    format=(
        "%(asctime)s - "
        "%(name)s - "
        "%(levelname)s - "
        "%(message)s"
    ),
)

logger = logging.getLogger(__name__)


# ============================================================
# APPLICATION
# ============================================================

app = FastAPI(
    title="FORMA-IA API",
    description=(
        "Plateforme intelligente de gestion "
        "de la formation pour ALTIORA."
    ),
    version="1.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
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

class LoggingMiddleware(
    BaseHTTPMiddleware
):

    async def dispatch(
        self,
        request: Request,
        call_next,
    ):

        start_time = time.time()

        logger.info(
            "Requête: %s %s",
            request.method,
            request.url.path,
        )

        response = await call_next(
            request
        )

        process_time = (
            time.time() - start_time
        )

        response.headers[
            "X-Process-Time"
        ] = f"{process_time:.3f}"

        logger.info(
            "Réponse: %s %s - "
            "Status: %s - "
            "Temps: %.3fs",
            request.method,
            request.url.path,
            response.status_code,
            process_time,
        )

        return response


app.add_middleware(
    LoggingMiddleware
)


# ============================================================
# ROUTES DE BASE
# ============================================================

@app.get("/")
async def root():

    return {
        "message": (
            "🚀 FORMA-IA API "
            "est en ligne !"
        ),
        "version": "1.0.0",
        "docs": "/api/docs",
    }


@app.get("/health")
async def health_check():

    return {
        "status": "healthy",
        "timestamp": (
            datetime.now().isoformat()
        ),
    }


# ============================================================
# ROUTES IA
# ============================================================

# FIX:
# Import direct des routers.
from app.api.v1.routes_veille import (
    router as veille_router
)

from app.api.v1.routes_tdr import (
    router as tdr_router
)


app.include_router(
    veille_router,
    prefix="/api/v1",
)

logger.info(
    "✅ Module M1 (Veille) chargé"
)


app.include_router(
    tdr_router,
    prefix="/api/v1",
)

logger.info(
    "✅ Module M2 (TDR) chargé"
)


# ============================================================
# STARTUP
# ============================================================

@app.on_event("startup")
async def startup():

    logger.info(
        "🚀 FORMA-IA API démarrage..."
    )

    logger.info(
        "📌 Environnement: %s",
        settings.ENVIRONMENT,
    )

    logger.info(
        "📌 Modèle OpenRouter: %s",
        getattr(
            settings,
            "OPENROUTER_MODEL",
            "non configuré",
        ),
    )

    logger.info(
        "✅ API prête"
    )

    logger.info(
        "📌 Documentation: "
        "http://localhost:8000/api/docs"
    )


# ============================================================
# SHUTDOWN
# ============================================================

@app.on_event("shutdown")
async def shutdown():

    logger.info(
        "🛑 FORMA-IA API arrêt..."
    )


# ============================================================
# POINT D'ENTRÉE
# ============================================================

if __name__ == "__main__":

    import uvicorn

    uvicorn.run(
        "app.main:app",
        host="127.0.0.1",
        port=8000,
        reload=True,
        log_level="info",
    )