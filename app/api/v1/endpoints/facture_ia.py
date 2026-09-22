# app/api/v1/endpoints/facture_ia.py
# ============================================================
# ROUTES IA — M7 (Facturation / relances)
# ============================================================
# ⚠️ Les routes HITL génériques (pending-reviews, approve, reject,
# stats) sont partagées entre TOUS les modules et vivent déjà sous
# /ia/formations/* (voir formation_ia.py) : elles ne sont PAS
# dupliquées ici. Une relance M7 en attente apparaît dans
# GET /ia/formations/pending-reviews?agent_id=agent_m7_relance et
# s'approuve via POST /ia/formations/reviews/{id}/approve — même
# pattern déjà utilisé par M3 et Préparation.
# ============================================================

import os
import time
import logging
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.orchestrator.facturation_orchestrator import (
    FacturationOrchestrator,
    get_facturation_orchestrator,
)
from app.schemas.facture_ia import CalculerMontantsRequest, GenererRelanceRequest

logger = logging.getLogger(__name__)

VERBOSE = os.getenv("VERBOSE_LOGS", "true").lower() == "true"


def vlog(msg: str, level: str = "info") -> None:
    if VERBOSE:
        getattr(logger, level)(msg)


# =============================================================================
# ROUTER
# =============================================================================
router = APIRouter(
    prefix="/ia/facturation",
    tags=["M7 — IA Facturation"],
)


# =============================================================================
# HELPERS
# =============================================================================

def _log_request(method: str, path: str, **kwargs) -> None:
    vlog("=" * 70)
    vlog(f"🌐 [Route M7] {method} {path}")
    for k, val in kwargs.items():
        vlog(f"   {k} : {val}")
    vlog("=" * 70)


def _handle_exception(e: Exception, context: str) -> None:
    if isinstance(e, ValueError):
        if "introuvable" in str(e).lower():
            raise HTTPException(status_code=404, detail=str(e))
        raise HTTPException(status_code=422, detail=f"Données invalides : {e}")
    if isinstance(e, RuntimeError):
        logger.error(f"❌ [Route M7] {context} — service : {e}")
        raise HTTPException(status_code=503, detail=str(e))
    logger.exception(f"💥 [Route M7] {context} : {e}")
    raise HTTPException(
        status_code=500,
        detail=f"Erreur interne : {type(e).__name__} — {e}",
    )


class RouteResponse(BaseModel):
    """Réponse standardisée pour les routes M7."""
    success: bool
    message: str
    duration_seconds: Optional[float] = None
    review_id: Optional[str] = None
    review_status: Optional[str] = None
    requires_human_action: bool = False
    data: Optional[Dict[str, Any]] = None


def _build_response(result: Dict[str, Any], msg_ok: str, elapsed: float) -> RouteResponse:
    review_id = result.get("_review_id") if isinstance(result, dict) else None
    status_val = result.get("_review_status") if isinstance(result, dict) else None
    requires_action = status_val == "pending_review"

    if isinstance(result, dict) and result.get("necessaire") is False:
        message = result.get("raison", "Aucune relance nécessaire.")
    else:
        message = msg_ok
        if requires_action:
            message += f" ⚠️ En attente validation (review={review_id})."

    return RouteResponse(
        success=True,
        message=message,
        duration_seconds=elapsed,
        review_id=review_id,
        review_status=status_val,
        requires_human_action=requires_action,
        data=result,
    )


# =============================================================================
# ROUTE 0 — GET /health
# =============================================================================

@router.get("/health", summary="[M7] État du module Facturation IA")
async def health_check() -> Dict[str, Any]:
    _log_request("GET", "/ia/facturation/health")
    try:
        from app.services.facturation import get_package_status
        return {"success": True, **get_package_status()}
    except Exception as e:
        _handle_exception(e, "health_check")
        return {"success": False}


# =============================================================================
# ROUTE 1 — POST /calculer-montants  (Python pur, sans LLM)
# =============================================================================

@router.post(
    "/calculer-montants",
    summary="[M7] Calculer les montants d'une facture (HT/TVA/TTC/remise)",
)
async def calculer_montants(payload: CalculerMontantsRequest) -> Dict[str, Any]:
    _log_request(
        "POST", "/ia/facturation/calculer-montants",
        Type=payload.type_client, Participants=payload.nb_participants,
    )
    try:
        from app.services.backend_sync.facture_calculator_service import (
            FactureCalculatorService,
        )
        service = FactureCalculatorService()
        result = service.calculer(
            type_client=payload.type_client,
            nb_participants=payload.nb_participants,
            tarif_unitaire=payload.tarif_unitaire,
            tva_taux=payload.tva_taux,
            remise_pct=payload.remise_pct,
            session_id=payload.session_id,
        )
        return result
    except Exception as e:
        _handle_exception(e, "calculer_montants")
        return {"success": False}


# =============================================================================
# ROUTE 2 — POST /relances/generer  (Agent M7 + HITL)
# =============================================================================

@router.post(
    "/relances/generer",
    response_model=RouteResponse,
    summary="[M7] Générer une relance (niveau 1/2/3 selon le retard) + HITL",
    description=(
        "1. Lit la facture côté Backend (GET /factures/{id})\n"
        "2. Calcule (Python) le montant restant dû, les jours de retard "
        "et le niveau d'escalade (1 rappel / 2 ferme / 3 mise en demeure)\n"
        "3. Génère le texte de la relance (LLM, secours Python si indisponible)\n"
        "4. Crée un review HITL — AUCUNE relance n'est envoyée sans validation "
        "humaine\n\n"
        "Si l'échéance n'est pas dépassée ou que la facture est déjà soldée, "
        "aucune relance n'est générée (`necessaire: false`).\n\n"
        "⚠️ Le Backend n'a pas encore de route pour stocker/envoyer une "
        "relance : une fois approuvée, le texte doit être transmis autrement "
        "pour l'instant."
    ),
)
async def generer_relance(
    payload: GenererRelanceRequest,
    orchestrator: FacturationOrchestrator = Depends(get_facturation_orchestrator),
) -> RouteResponse:
    _log_request("POST", "/ia/facturation/relances/generer", Facture=payload.facture_id)
    start = time.perf_counter()
    try:
        result = await orchestrator.generer_relance(facture_id=payload.facture_id)
        elapsed = round(time.perf_counter() - start, 2)
        vlog(f"✅ [Route M7] relances/generer OK en {elapsed}s")
        return _build_response(result, "Relance générée.", elapsed)
    except Exception as e:
        _handle_exception(e, "generer_relance")
        return RouteResponse(success=False, message="")
