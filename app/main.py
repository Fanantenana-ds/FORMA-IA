from fastapi import FastAPI

from app.database import Base, engine
from app.models.user import User
from app.models.revoked_token import RevokedToken
from app.models.opportunite import Opportunite
from app.models.historique_analyse import HistoriqueAnalyse
from app.api.v1.router import api_router


Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="FORMA-IA API"
)

app.include_router(
    api_router,
    prefix="/api/v1"
)
