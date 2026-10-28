# app/api/v1/endpoints/vocal_ia.py
# ============================================================
# ROUTES IA — Agent vocal FORMA-IA
# ============================================================
# POST /ia/vocal/commande  — analyse une commande vocale
# GET  /ia/vocal/health    — santé du service
# ============================================================

import logging
import time
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.services.vocal.routeur_vocal import router_commande
from app.utils.security import verify_api_key

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/ia/vocal",
    tags=["Vocal — Agent vocal FORMA-IA"],
    dependencies=[Depends(verify_api_key)],
)


# ──────────────────────────────────────────────────────────────
# Schémas
# ──────────────────────────────────────────────────────────────

class CommandeVocaleRequest(BaseModel):
    texte: str = Field(..., min_length=1, max_length=500, description="Texte transcrit depuis la voix")
    formations_disponibles: list[str] = Field(
        default_factory=list,
        description="Liste des noms de formations disponibles (contexte optionnel)",
    )


class CommandeVocaleResponse(BaseModel):
    intention: str
    confiance: float
    parametres: dict[str, Any]
    parametres_manquants: list[str]
    reponse_vocale: str
    action_frontend: str | None
    prefill: dict[str, Any]
    duree_ms: int


# ──────────────────────────────────────────────────────────────
# Routes
# ──────────────────────────────────────────────────────────────

@router.post(
    "/commande",
    response_model=CommandeVocaleResponse,
    summary="Analyser une commande vocale",
    description=(
        "Reçoit un texte transcrit depuis la reconnaissance vocale, "
        "détecte l'intention, extrait les paramètres et retourne "
        "l'action à exécuter sur le frontend et la réponse à lire à voix haute."
    ),
)
async def analyser_commande(req: CommandeVocaleRequest) -> CommandeVocaleResponse:
    debut = time.time()
    logger.info("🎤 Commande vocale reçue : '%s'", req.texte[:80])

    try:
        result = await router_commande(
            commande=req.texte,
            formations=req.formations_disponibles,
        )
    except Exception as e:
        logger.error("Erreur routeur vocal : %s", e)
        raise HTTPException(status_code=500, detail="Erreur interne du routeur vocal.")

    duree = int((time.time() - debut) * 1000)
    logger.info(
        "🎤 Intention : %s (confiance=%.2f) — %d ms",
        result.get("intention"),
        result.get("confiance", 0),
        duree,
    )

    return CommandeVocaleResponse(
        intention=result.get("intention", "hors_perimetre"),
        confiance=result.get("confiance", 0.0),
        parametres=result.get("parametres", {}),
        parametres_manquants=result.get("parametres_manquants", []),
        reponse_vocale=result.get("reponse_vocale", ""),
        action_frontend=result.get("action_frontend"),
        prefill=result.get("prefill", {}),
        duree_ms=duree,
    )


@router.get(
    "/health",
    summary="Santé du service vocal",
)
async def health() -> dict:
    return {"status": "ok", "service": "agent_vocal_forma_ia"}
