from fastapi import APIRouter


from app.api.v1.endpoints import auth, opportunite, facture, document, formation, dashboard,formation_ia,offre_ia


api_router = APIRouter()

api_router.include_router(auth.router)
api_router.include_router(opportunite.router)
api_router.include_router(formation.router)
api_router.include_router(formation.participants_router)
api_router.include_router(dashboard.router)
api_router.include_router(formation_ia.router)
api_router.include_router(facture.router)
api_router.include_router(offre_ia.router)