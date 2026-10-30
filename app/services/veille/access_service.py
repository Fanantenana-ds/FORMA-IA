"""Accès M1 : session Backend existante ou clé interne historique."""
import secrets

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user
from app.database import get_db
from app.utils import security


def verify_api_key(
    credentials: HTTPAuthorizationCredentials | None = Depends(HTTPBearer(auto_error=False)),
    db: Session = Depends(get_db),
):
    if credentials and security.SHARED_INTERNAL_TOKEN and secrets.compare_digest(
        credentials.credentials, security.SHARED_INTERNAL_TOKEN
    ):
        return None
    # Réutilise les contrôles existants : signature, expiration, révocation,
    # utilisateur présent et compte actif. Aucun décodage JWT parallèle.
    return get_current_user(credential=credentials, db=db)


def verify_api_key_sse(
    token: str | None = None,
    credentials: HTTPAuthorizationCredentials | None = Depends(HTTPBearer(auto_error=False)),
    db: Session = Depends(get_db),
):
    # Compatibilité de la page de démonstration historique ; les nouvelles
    # sessions utilisateur passent exclusivement par le header Bearer.
    if token and security.SHARED_INTERNAL_TOKEN and secrets.compare_digest(token, security.SHARED_INTERNAL_TOKEN):
        return None
    return verify_api_key(credentials=credentials, db=db)
