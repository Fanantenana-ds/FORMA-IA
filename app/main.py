from fastapi import FastAPI

from app.database import Base, engine
from app.models.user import User
from app.models.revoked_token import RevokedToken
from app.api.v1.auth import router as auth_router

Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="FORMA-IA API"
)

app.include_router(auth_router)
