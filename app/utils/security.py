# app/utils/security.py
# ============================================================
# PROTECTION DES ENDPOINTS IA — JWT UTILISATEUR OU CLÉ INTERNE
# ============================================================
# Les sessions du frontend sont validées par le mécanisme JWT central.
# La clé interne reste acceptée pour les appels de service à service.
# ============================================================

import logging
import os
import secrets

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user
from app.database import get_db

logger = logging.getLogger(__name__)

SHARED_INTERNAL_TOKEN = os.getenv("SHARED_INTERNAL_TOKEN") or os.getenv("IA_API_KEY")

if not SHARED_INTERNAL_TOKEN:
    logger.warning(
        "⚠️ SHARED_INTERNAL_TOKEN non définie dans .env — les endpoints IA "
        "refuseront TOUTES les requêtes. Génère-en une avec : "
        "python -c \"import secrets; print(secrets.token_urlsafe(32))\""
    )

# auto_error=False : on gère nous-mêmes le message d'erreur plutôt
# que de laisser FastAPI renvoyer une 403 générique peu explicite.
# C'est aussi ce qui fait apparaître le bouton "Authorize" (cadenas)
# en haut de Swagger UI, où tu colles la clé brute SANS taper
# "Bearer " toi-même — Swagger l'ajoute automatiquement.
_bearer_scheme = HTTPBearer(auto_error=False)


async def verify_api_key(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
    db: Session = Depends(get_db),
):
    """
    Dépendance FastAPI à ajouter sur les routes à protéger.
    Les utilisateurs peuvent envoyer leur JWT de session. Les appels
    internes peuvent continuer à envoyer SHARED_INTERNAL_TOKEN.

    Usage (protège TOUTES les routes d'un routeur en une ligne) :
        router = APIRouter(dependencies=[Depends(verify_api_key)])
    """

    if (
        credentials
        and SHARED_INTERNAL_TOKEN
        and secrets.compare_digest(credentials.credentials, SHARED_INTERNAL_TOKEN)
    ):
        return None

    # Les interfaces connectées utilisent leur JWT utilisateur. On délègue
    # sa validation au mécanisme central (signature, expiration, révocation,
    # compte actif) au lieu de demander un secret interne au navigateur.
    return get_current_user(request=request, credential=credentials, db=db)


async def verify_api_key_sse(
    token: str | None = None,
    credentials: HTTPAuthorizationCredentials | None = Depends(
        HTTPBearer(auto_error=False)
    ),
) -> None:
    """Variante SSE : accepte le token en query param ?token= ou en header Bearer.

    EventSource (navigateur) ne peut pas envoyer de headers — le token
    doit donc pouvoir transiter par l'URL pour les routes SSE.
    """
    if not SHARED_INTERNAL_TOKEN:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="SHARED_INTERNAL_TOKEN non configurée côté serveur.",
        )

    raw = token or (credentials.credentials if credentials else None)

    if not raw:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentification requise : token manquant (header Bearer ou ?token=).",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not secrets.compare_digest(raw, SHARED_INTERNAL_TOKEN):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Clé API invalide.",
            headers={"WWW-Authenticate": "Bearer"},
        )
