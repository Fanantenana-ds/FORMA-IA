# app/services/backend_sync/opportunity_fetcher.py
# ============================================================
# FETCH OPPORTUNITÉ — Récupère une opportunité depuis le Backend
# ============================================================
# Ce service permet au M2 (TDR) de récupérer les données d'une
# opportunité détectée par M1 (Veille) pour pré-remplir le brief.
# ============================================================

import logging
import os
from typing import Any, Dict, List, Optional

import httpx

logger = logging.getLogger(__name__)

# ============================================================
# CONFIGURATION
# ============================================================
BACKEND_API_URL = os.getenv("BACKEND_API_URL", "http://localhost:8000/api/v1")
BACKEND_SYNC_TOKEN = os.getenv("BACKEND_SYNC_TOKEN", "")
BACKEND_SERVICE_EMAIL = os.getenv("BACKEND_SERVICE_EMAIL", "")
BACKEND_SERVICE_PASSWORD = os.getenv("BACKEND_SERVICE_PASSWORD", "")
BACKEND_FETCH_TIMEOUT = float(os.getenv("BACKEND_FETCH_TIMEOUT", "15"))


# ============================================================
# AUTO-LOGIN (même logique que sync)
# ============================================================

async def _get_backend_token() -> Optional[str]:
    """Récupère un JWT token (env ou auto-login)."""
    if BACKEND_SYNC_TOKEN:
        return BACKEND_SYNC_TOKEN

    if not BACKEND_SERVICE_EMAIL or not BACKEND_SERVICE_PASSWORD:
        logger.warning("⚠️ Pas de credentials pour fetch")
        return None

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                f"{BACKEND_API_URL}/auth/login",
                json={
                    "email": BACKEND_SERVICE_EMAIL,
                    "password": BACKEND_SERVICE_PASSWORD,
                },
            )
            if response.status_code == 200:
                return response.json().get("access_token")
    except Exception as exc:
        logger.error("❌ Auto-login échoué : %s", exc)

    return None


# ============================================================
# FETCH — Opportunité unique
# ============================================================

async def fetch_opportunite_by_id(
    opportunite_id: str,
) -> Optional[Dict[str, Any]]:
    """
    Récupère une opportunité par son ID depuis le Backend.

    Endpoint Backend attendu : GET /api/v1/opportunites/{id}

    Retourne :
      - Dict de l'opportunité si trouvée
      - None si erreur ou non trouvée
    """
    if not opportunite_id:
        return None

    token = await _get_backend_token()
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    try:
        async with httpx.AsyncClient(timeout=BACKEND_FETCH_TIMEOUT) as client:
            response = await client.get(
                f"{BACKEND_API_URL}/opportunites/{opportunite_id}",
                headers=headers,
            )

            if response.status_code == 200:
                data = response.json()
                logger.info(
                    "✅ Opportunité récupérée : %s", opportunite_id
                )
                return data

            elif response.status_code == 404:
                logger.warning(
                    "⚠️ Opportunité introuvable : %s", opportunite_id
                )
                return None

            else:
                logger.error(
                    "❌ Erreur fetch : HTTP %d | %s",
                    response.status_code,
                    response.text[:200]
                )
                return None

    except httpx.TimeoutException:
        logger.error("❌ Timeout fetch : %s", opportunite_id)
        return None
    except Exception as exc:
        logger.exception("❌ Erreur fetch : %s", exc)
        return None


# ============================================================
# FETCH — Liste d'opportunités
# ============================================================

async def fetch_opportunites_list(
    limit: int = 50,
    statut: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    Récupère la liste des opportunités (pour Frontend).

    Endpoint Backend attendu : GET /api/v1/opportunites
    """
    token = await _get_backend_token()
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    params = {"limit": limit}
    if statut:
        params["statut"] = statut

    try:
        async with httpx.AsyncClient(timeout=BACKEND_FETCH_TIMEOUT) as client:
            response = await client.get(
                f"{BACKEND_API_URL}/opportunites",
                headers=headers,
                params=params,
            )

            if response.status_code == 200:
                data = response.json()
                # Gérer les 2 formats possibles
                opps = (
                    data.get("opportunites")
                    or data.get("items")
                    or (data if isinstance(data, list) else [])
                )
                logger.info("✅ %d opportunités récupérées", len(opps))
                return opps
            else:
                logger.error(
                    "❌ Erreur fetch list : HTTP %d",
                    response.status_code
                )
                return []

    except Exception as exc:
        logger.exception("❌ Erreur fetch list : %s", exc)
        return []


# ============================================================
# MAPPING — Opportunité → Brief TDR
# ============================================================

def opportunity_to_brief(opportunite: Dict[str, Any]) -> Dict[str, Any]:
    """
    Convertit une opportunité en brief pour M2.

    Mapping :
      - objet (opportunité)    → objectifs (brief)
      - source (opportunité)   → client (brief)
      - budget (opportunité)   → budget (brief)
      - contenu (opportunité)  → contexte supplémentaire

    Les champs manquants (public, durée, lieu) sont laissés VIDES
    pour que l'utilisateur les complète manuellement.
    """
    if not opportunite:
        return {}

    # Budget : convertir float → string formaté
    budget_raw = opportunite.get("budget", 0) or 0
    try:
        budget_value = float(budget_raw)
        if budget_value > 0:
            budget = f"{int(budget_value):,} Ar".replace(",", " ")
        else:
            budget = ""
    except (ValueError, TypeError):
        budget = str(budget_raw) if budget_raw else ""

    # Construire les objectifs (objet + éventuellement contenu)
    objet = opportunite.get("objet", "") or opportunite.get("title", "")
    contenu = opportunite.get("contenu", "") or opportunite.get("summary", "")

    objectifs = objet
    if contenu and contenu != objet:
        objectifs = f"{objet}\n\n{contenu[:500]}"

    return {
        "client": opportunite.get("source", ""),
        "objectifs": objectifs,
        "public": "",           # ⚠️ À compléter par l'utilisateur
        "duree": "",            # ⚠️ À compléter par l'utilisateur
        "format": "Présentiel",
        "budget": budget,
        "lieu": "",             # ⚠️ À compléter par l'utilisateur
        "opportunite_id": opportunite.get("id"),
    }