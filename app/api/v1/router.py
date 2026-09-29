from fastapi import APIRouter

from app.api.v1.endpoints import (
    analyse,
    auth,
    dashboard,
    document,
    facture,
    facture_ia,
    formation,
    formation_ia,
    offre_ia,
    opportunite,
    preparation_ia,
)

api_router = APIRouter()

api_router.include_router(auth.router)
api_router.include_router(opportunite.router)
api_router.include_router(analyse.router)
api_router.include_router(document.router)
api_router.include_router(formation.router)
api_router.include_router(formation.participants_router)
api_router.include_router(dashboard.router)
api_router.include_router(formation_ia.router)
api_router.include_router(facture.router)
api_router.include_router(offre_ia.router)
api_router.include_router(preparation_ia.router)
api_router.include_router(facture_ia.router)