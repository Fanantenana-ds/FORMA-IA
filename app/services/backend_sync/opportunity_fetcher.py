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

from app.services.backend_sync import base_sync

logger = logging.getLogger(__name__)

# ============================================================
# CONFIGURATION
# ============================================================
# URL, token, login automatique et re-login sur 401 : base_sync.py
BACKEND_FETCH_TIMEOUT = float(os.getenv("BACKEND_FETCH_TIMEOUT", "15"))


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

    response = await base_sync.backend_request(
        "GET",
        f"/opportunites/{opportunite_id}",
        timeout=BACKEND_FETCH_TIMEOUT,
    )

    if response["ok"]:
        logger.info("✅ Opportunité récupérée : %s", opportunite_id)
        return response["data"]

    if response["status_code"] == 404:
        logger.warning("⚠️ Opportunité introuvable : %s", opportunite_id)
    else:
        logger.error("❌ Erreur fetch : %s", response["error"])
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
    params: Dict[str, Any] = {"limit": limit}
    if statut:
        params["statut"] = statut

    response = await base_sync.backend_request(
        "GET",
        "/opportunites",
        params=params,
        timeout=BACKEND_FETCH_TIMEOUT,
    )

    if not response["ok"]:
        logger.error("❌ Erreur fetch list : %s", response["error"])
        return []

    data = response["data"]
    # Gérer les formats possibles (liste directe, {"opportunites"}, {"items"})
    if isinstance(data, list):
        opps = data
    elif isinstance(data, dict):
        opps = data.get("opportunites") or data.get("items") or []
    else:
        opps = []

    logger.info("✅ %d opportunités récupérées", len(opps))
    return opps


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