from fastapi import APIRouter

from app.api.v1.endpoints import auth, opportunite, analyse

api_router = APIRouter()

api_router.include_router(auth.router)
api_router.include_router(opportunite.router)
api_router.include_router(analyse.router)