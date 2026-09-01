# app/utils/security.py
# ============================================================
# PROTECTION LÉGÈRE DES ENDPOINTS IA — CLÉ API BEARER
# ============================================================
# Ceci N'EST PAS le système d'authentification JWT + rôles du
# CDC (§4) — celui-là est la responsabilité du module Backend
# (voir répartition des rôles). C'est une protection immédiate,
# légère, que TU contrôles, pour empêcher que tes endpoints IA
# (qui consomment TES clés Groq/Tavily) soient appelés sans
# autorisation pendant que le vrai système JWT est en cours de
# construction côté Backend.
#
# Les deux systèmes coexisteront : ce garde-fou peut rester en
# complément, ou être retiré une fois le JWT backend intégré à
# tes routes IA.
# ============================================================

import logging
import os
import secrets

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

logger = logging.getLogger(__name__)

IA_API_KEY = os.getenv("IA_API_KEY")

if not IA_API_KEY:
    logger.warning(
        "⚠️ IA_API_KEY non définie dans .env — les endpoints IA "
        "protégés par verify_api_key refuseront TOUTES les requêtes "
        "tant qu'une clé n'est pas configurée. Génère-en une avec : "
        "python -c \"import secrets; print(secrets.token_urlsafe(32))\""
    )

# auto_error=False : on gère nous-mêmes le message d'erreur plutôt
# que de laisser FastAPI renvoyer une 403 générique peu explicite.
# C'est aussi ce qui fait apparaître le bouton "Authorize" (cadenas)
# en haut de Swagger UI, où tu colles la clé brute SANS taper
# "Bearer " toi-même — Swagger l'ajoute automatiquement.
_bearer_scheme = HTTPBearer(auto_error=False)


async def verify_api_key(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer_scheme),
) -> None:
    """
    Dépendance FastAPI à ajouter sur les routes à protéger.
    Dans Swagger UI : clique sur le cadenas "Authorize" en haut de
    la page, colle la clé BRUTE (sans "Bearer "), valide.

    Usage (protège TOUTES les routes d'un routeur en une ligne) :
        router = APIRouter(dependencies=[Depends(verify_api_key)])
    """

    if not IA_API_KEY:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="IA_API_KEY non configurée côté serveur.",
        )

    if credentials is None or not credentials.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentification requise : clé API manquante.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Comparaison à temps constant : évite les attaques par mesure
    # du temps de réponse pour deviner la clé caractère par caractère.
    if not secrets.compare_digest(credentials.credentials, IA_API_KEY):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Clé API invalide.",
            headers={"WWW-Authenticate": "Bearer"},
        )