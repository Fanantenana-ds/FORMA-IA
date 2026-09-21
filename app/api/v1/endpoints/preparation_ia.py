import os
import time
import logging
from typing import Dict, Any, Optional, List

from fastapi import APIRouter, HTTPException, Depends, status
from pydantic import BaseModel, Field

from app.orchestrator.preparation_orchestrator import (
    PreparationOrchestrator,
    get_preparation_orchestrator,
)

logger = logging.getLogger(__name__)

VERBOSE = os.getenv("VERBOSE_LOGS", "true").lower() == "true"


def vlog(msg: str, level: str = "info") -> None:
    if VERBOSE:
        getattr(logger, level)(msg)


# =============================================================================
# ROUTER
# =============================================================================
router = APIRouter(
    prefix="/ia/preparation",
    tags=["Préparation — IA"],
)


# =============================================================================
# HELPERS
# =============================================================================

def _log_request(method: str, path: str, **kwargs) -> None:
    vlog("=" * 70)
    vlog(f"🌐 [Route PREP] {method} {path}")
    for k, val in kwargs.items():
        vlog(f"   {k} : {val}")
    vlog("=" * 70)


def _handle_exception(e: Exception, context: str) -> None:
    if isinstance(e, NotImplementedError):
        raise HTTPException(status_code=501, detail=str(e))
    if isinstance(e, ValueError):
        logger.error(f"❌ [Route PREP] {context} — validation : {e}")
        raise HTTPException(status_code=422, detail=f"Données invalides : {e}")
    if isinstance(e, RuntimeError):
        logger.error(f"❌ [Route PREP] {context} — service : {e}")
        raise HTTPException(status_code=503, detail=str(e))
    logger.exception(f"💥 [Route PREP] {context} : {e}")
    raise HTTPException(
        status_code=500,
        detail=f"Erreur interne : {type(e).__name__} — {e}",
    )


def _build_response(result: Dict[str, Any], msg_ok: str, elapsed: float) -> "RouteResponse":
    """Construit la réponse uniforme avec info HITL."""
    review_id = result.get("_review_id") if isinstance(result, dict) else None
    status_val = result.get("_review_status") if isinstance(result, dict) else None

    requires_action = status_val == "pending_review"
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
# SCHÉMAS — REQUÊTES
# =============================================================================

class CalculateBudgetRequest(BaseModel):
    formateur_info: Dict[str, Any] = Field(..., description="Infos formateur")
    salle_info: Dict[str, Any] = Field(..., description="Infos salle")
    nb_jours: int = Field(..., ge=1, le=30)
    nb_participants: int = Field(..., ge=1, le=500)
    options: Dict[str, Any] = Field(default_factory=dict)

    class Config:
        json_schema_extra = {
            "example": {
                "formateur_info": {"nom": "Rakoto", "tarif_journalier": 500000},
                "salle_info": {"nom": "Salle A", "tarif_journalier": 200000},
                "nb_jours": 2,
                "nb_participants": 20,
            }
        }


class GenerateEDTRequest(BaseModel):
    titre_formation: str = Field(..., min_length=3)
    modules: List[Dict[str, Any]] = Field(..., min_length=1)
    dates: List[str] = Field(..., min_length=1)
    formateur: Optional[Dict[str, Any]] = None
    salle: Optional[Dict[str, Any]] = None

    class Config:
        json_schema_extra = {
            "example": {
                "titre_formation": "Introduction à l'IA",
                "modules": [
                    {"titre": "Introduction", "duree": "3h"},
                    {"titre": "Apprentissage", "duree": "3h"},
                ],
                "dates": ["2026-10-15", "2026-10-16"],
                "formateur": {"nom": "M. RANAIVOSOA", "specialite": "IA"},
                "salle": {"nom": "Salle A"},
            }
        }


class GenerateCompleteRequest(BaseModel):
    offre_data: Dict[str, Any] = Field(..., description="Données offre (M3)")
    projet_info: Dict[str, Any] = Field(..., description="Infos projet")
    ressources: Dict[str, Any] = Field(..., description="{formateur, salle}")
    options: Dict[str, Any] = Field(default_factory=dict)

    class Config:
        json_schema_extra = {
            "example": {
                "offre_data": {
                    "reference": "ALT-OFF-TECH-2026-0001",
                    "titre": "Introduction à l'IA",
                    "duree_jours": 2,
                    "modules": [
                        {"titre": "Introduction", "duree": "3h"},
                        {"titre": "Apprentissage", "duree": "3h"},
                    ],
                },
                "projet_info": {
                    "id": 1,
                    "client": "Ministère de l'Éducation",
                    "client_id": 1,
                    "nb_participants": 20,
                },
                "ressources": {
                    "formateur": {"nom": "M. RANAIVOSOA", "tarif_journalier": 500000},
                    "salle": {"nom": "Salle A", "tarif_journalier": 200000},
                },
                "options": {
                    "date_debut": "2026-10-15",
                    "date_fin": "2026-10-16",
                },
            }
        }


class RegenerateRequest(BaseModel):
    review_id: str = Field(..., description="ID du review rejeté")
    feedback: str = Field(..., min_length=10)


class SynchroniserRequest(BaseModel):
    review_id: str = Field(
        ..., description="ID du review APPROUVÉ de la préparation (agent_preparation)"
    )
    formateur_id: Optional[str] = Field(
        default=None, description="UUID d'un utilisateur Backend (facultatif)"
    )
    force: bool = Field(
        default=False,
        description="Renvoyer même si déjà synchronisé (crée une NOUVELLE session côté Backend)",
    )


# =============================================================================
# SCHÉMAS — RÉPONSES
# =============================================================================

class RouteResponse(BaseModel):
    success: bool
    message: str
    duration_seconds: Optional[float] = None
    review_id: Optional[str] = None
    review_status: Optional[str] = None
    requires_human_action: bool = False
    data: Optional[Dict[str, Any]] = None


# =============================================================================
# ROUTE 0 — GET /health
# =============================================================================

@router.get("/health", summary="[PREP] État du module Préparation")
async def health_check() -> Dict[str, Any]:
    _log_request("GET", "/ia/preparation/health")
    try:
        from app.services.preparation import get_package_status
        return {"success": True, **get_package_status()}
    except Exception as e:
        _handle_exception(e, "health_check")
        return {"success": False}


# =============================================================================
# ROUTE 1 — POST /calculer-budget
# =============================================================================

@router.post(
    "/calculer-budget",
    response_model=RouteResponse,
    summary="[PREP] Calculer le budget prévisionnel (Python pur)",
)
async def calculer_budget(
    payload: CalculateBudgetRequest,
    orchestrator: PreparationOrchestrator = Depends(get_preparation_orchestrator),
) -> RouteResponse:
    _log_request(
        "POST", "/ia/preparation/calculer-budget",
        Formateur=payload.formateur_info.get("nom", "N/A"),
        Jours=payload.nb_jours,
    )
    start = time.perf_counter()
    try:
        result = orchestrator.calculer_budget(
            formateur_info=payload.formateur_info,
            salle_info=payload.salle_info,
            nb_jours=payload.nb_jours,
            nb_participants=payload.nb_participants,
            options=payload.options,
        )
        elapsed = round(time.perf_counter() - start, 2)
        vlog(f"✅ [Route PREP] calculer-budget OK en {elapsed}s")
        return RouteResponse(
            success=True,
            message="Budget calculé.",
            duration_seconds=elapsed,
            data=result,
        )
    except Exception as e:
        _handle_exception(e, "calculer_budget")
        return RouteResponse(success=False, message="")


# =============================================================================
# ROUTE 2 — POST /generer-edt
# =============================================================================

@router.post(
    "/generer-edt",
    response_model=RouteResponse,
    summary="[PREP] Générer l'emploi du temps (LLM)",
)
async def generer_edt(
    payload: GenerateEDTRequest,
    orchestrator: PreparationOrchestrator = Depends(get_preparation_orchestrator),
) -> RouteResponse:
    _log_request(
        "POST", "/ia/preparation/generer-edt",
        Formation=payload.titre_formation,
        Jours=len(payload.dates),
    )
    start = time.perf_counter()
    try:
        result = await orchestrator.generer_edt(
            titre_formation=payload.titre_formation,
            modules=payload.modules,
            dates=payload.dates,
            formateur=payload.formateur,
            salle=payload.salle,
        )
        elapsed = round(time.perf_counter() - start, 2)
        vlog(f"✅ [Route PREP] generer-edt OK en {elapsed}s")
        return RouteResponse(
            success=True,
            message="EDT généré.",
            duration_seconds=elapsed,
            data=result,
        )
    except Exception as e:
        _handle_exception(e, "generer_edt")
        return RouteResponse(success=False, message="")


# =============================================================================
# ROUTE 3 — POST /generer-complet ⭐
# =============================================================================

@router.post(
    "/generer-complet",
    response_model=RouteResponse,
    summary="[PREP] ⭐ Générer la préparation complète (Budget + EDT + HITL)",
    description=(
        "Route principale du module Préparation.\n\n"
        "1. Calcule le budget prévisionnel (Python pur)\n"
        "2. Génère l'emploi du temps (LLM)\n"
        "3. Crée un review HITL (validation humaine obligatoire)\n\n"
        "⚠️ La validation humaine doit approuver avant démarrage."
    ),
)
async def generer_complet(
    payload: GenerateCompleteRequest,
    orchestrator: PreparationOrchestrator = Depends(get_preparation_orchestrator),
) -> RouteResponse:
    _log_request(
        "POST", "/ia/preparation/generer-complet",
        Offre=payload.offre_data.get("reference", "N/A"),
        Client=payload.projet_info.get("client", "N/A"),
    )
    start = time.perf_counter()
    try:
        result = await orchestrator.generate_complete(
            offre_data=payload.offre_data,
            projet_info=payload.projet_info,
            ressources=payload.ressources,
            options=payload.options,
        )
        elapsed = round(time.perf_counter() - start, 2)
        vlog(f"✅ [Route PREP] generer-complet OK en {elapsed}s")
        return _build_response(result, "Préparation complète générée.", elapsed)
    except Exception as e:
        _handle_exception(e, "generer_complet")
        return RouteResponse(success=False, message="")


# =============================================================================
# ROUTE 4 — POST /regenerer
# =============================================================================

@router.post(
    "/regenerer",
    response_model=RouteResponse,
    summary="[PREP] Régénérer une préparation rejetée",
)
async def regenerer(
    payload: RegenerateRequest,
    orchestrator: PreparationOrchestrator = Depends(get_preparation_orchestrator),
) -> RouteResponse:
    _log_request(
        "POST", "/ia/preparation/regenerer",
        Review=payload.review_id,
        Feedback=payload.feedback[:80],
    )
    start = time.perf_counter()
    try:
        result = await orchestrator.regenerate(
            review_id=payload.review_id,
            feedback=payload.feedback,
        )
        elapsed = round(time.perf_counter() - start, 2)
        vlog(f"✅ [Route PREP] regenerer OK en {elapsed}s")
        return _build_response(result, "Préparation régénérée.", elapsed)
    except Exception as e:
        _handle_exception(e, "regenerer")
        return RouteResponse(success=False, message="")


# =============================================================================
# ROUTE 5 — POST /synchroniser  (Backend, APRÈS approbation HITL)
# =============================================================================

@router.post(
    "/synchroniser",
    response_model=RouteResponse,
    summary="[PREP] Enregistrer une préparation APPROUVÉE dans le Backend",
    description=(
        "Enregistre l'EDT dans le Backend : une session (POST /sessions) et "
        "une séance par jour d'EDT.\n\n"
        "⚠️ Refusé (422) tant que le review n'est pas **approuvé**.\n\n"
        "Le **budget n'est pas persisté** : le Backend n'a pas de route pour "
        "lui (`data.backend_sync.budget.skipped`). Un seul envoi par review "
        "(sauf `force`). Nécessite BACKEND_SYNC_ENABLED=true."
    ),
)
async def synchroniser(
    payload: SynchroniserRequest,
    orchestrator: PreparationOrchestrator = Depends(get_preparation_orchestrator),
) -> RouteResponse:
    from app.services.backend_sync.review_sync import describe_sync

    _log_request(
        "POST", "/ia/preparation/synchroniser",
        Review=payload.review_id,
        Force=payload.force,
    )
    start = time.perf_counter()
    try:
        result = await orchestrator.synchroniser_backend(
            review_id=payload.review_id,
            formateur_id=payload.formateur_id,
            force=payload.force,
        )
        elapsed = round(time.perf_counter() - start, 2)
        success, message = describe_sync(result)
        vlog(f"✅ [Route PREP] synchroniser terminé en {elapsed}s : {message}")
        return RouteResponse(
            success=success,
            message=message,
            duration_seconds=elapsed,
            review_id=payload.review_id,
            review_status="approved",
            requires_human_action=False,
            data=result,
        )
    except Exception as e:
        _handle_exception(e, "synchroniser")
        return RouteResponse(success=False, message="")