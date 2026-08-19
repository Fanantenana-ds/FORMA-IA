from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer

from sqlalchemy.orm import Session

from app.database import get_db
from app.core.security import decode_access_token
from app.repositories.user_repository import UserRepository
from app.repositories.revoked_token_repository import (
    RevokedTokenRepository
)
from typing import Callable

oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl="/auth/login"
    )

def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    # Décodage et vérification du JWT
    payload = decode_access_token(token)

    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token invalide ou expiré",
            headers={
                "WWW-Authenticate": "Bearer"
            }
        )

    # Récupérationdes informations du JWT
    user_id = payload.get("sub")
    jti = payload.get("jti")

    if not user_id or not jti:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token invalide",
            headers={
                "WWW-Authenticate": "Bearer"
            }
        )

    # Vérification si le JWT a été révoqué
    revoked_repository = RevokedTokenRepository(db)

    if revoked_repository.exist_by_jti(jti):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token révoqué",
            headers={
                "WWW-Authenticate": "Bearer"
            }
        )

    # Récupération de l'utilisateur
    user_repository = UserRepository(db)

    user = user_repository.find_by_id(user_id)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Utilisateur introuvable",
            headers={
                "WWW-Authenticate": "Bearer"
            }
        )

    # Vérification du compte si il est toujours actif
    if not user.actif:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Ce compte est désactivé"
        )

    return user

def require_role(*allowed_roles: str) -> Callable:

    def role_checker(current_user = Depends(get_current_user)):
        user_role = (
            current_user.role.value
            if hasattr(current_user.role, "value")
            else current_user.role
        )

        if user_role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Vous n'avez pas les permissions nécessaires"
            )

        return current_user

    return role_checker