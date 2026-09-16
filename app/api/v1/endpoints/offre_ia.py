import os
import time
import logging
from typing import Dict, Any, Optional, List

from fastapi import APIRouter, HTTPException, Depends, status
from pydantic import BaseModel, Field

from app.orchestrator.offre_orchestrator import (
    OffreOrchestrator,
    get_offre_orchestrator,
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
    prefix="/ia/offres",
    tags=["M3 — IA Offres"],
)


# =============================================================================
# HELPERS
# =============================================================================

def _log_request(method: str, path: str, **kwargs) -> None:
    vlog("=" * 70)
    vlog(f"🌐 [Route M3] {method} {path}")
    for k, val in kwargs.items():
        vlog(f"   {k} : {val}")
    vlog("=" * 70)


def _handle_exception(e: Exception, context: str) -> None:
    if isinstance(e, NotImplementedError):
        logger.warning(f"⚠️  [Route M3] {context} : {e}")
        raise HTTPException(status_code=501, detail=str(e))
    if isinstance(e, ValueError):
        logger.error(f"❌ [Route M3] {context} — validation : {e}")
        raise HTTPException(status_code=422, detail=f"Données invalides : {e}")
    if isinstance(e, RuntimeError):
        logger.error(f"❌ [Route M3] {context} — service : {e}")
        raise HTTPException(status_code=503, detail=str(e))
    logger.exception(f"💥 [Route M3] {context} : {e}")
    raise HTTPException(
        status_code=500,
        detail=f"Erreur interne : {type(e).__name__} — {e}",
    )


def _build_response(result: Dict[str, Any], msg_ok: str, elapsed: float) -> "RouteResponse":
    """Construit une réponse uniforme avec info HITL."""
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

class GenerateTechniqueRequest(BaseModel):
    """Corps de la requête pour générer uniquement l'offre technique."""
    tdr_data: Dict[str, Any] = Field(..., description="Données du TDR (issu du M2)")
    session_info: Dict[str, Any] = Field(..., description="Informations de session")


class GenerateFinanciereRequest(BaseModel):
    """Corps de la requête pour générer uniquement l'offre financière."""
    offre_technique: Dict[str, Any] = Field(
        ...,
        description="Offre technique (issue du M3-1)",
    )
    options: Dict[str, Any] = Field(
        default_factory=dict,
        description="Options (type_formateur, type_salle, nb_participants, tva_applicable)",
    )


class GenerateCompleteRequest(BaseModel):
    """Corps de la requête pour générer une offre complète (⭐ principal)."""
    tdr_data: Dict[str, Any] = Field(..., description="Données du TDR")
    session_info: Dict[str, Any] = Field(..., description="Informations de session")
    options: Dict[str, Any] = Field(
        default_factory=dict,
        description=(
            "Options : "
            "nb_participants (int), "
            "type_formateur (senior/junior), "
            "type_salle (standard/premium), "
            "tva_applicable (bool), "
            "inclure_logistique (bool), "
            "inclure_administration (bool)"
        ),
    )

    class Config:
        json_schema_extra = {
            "example": {
                "tdr_data": {
                    "id": 1,
                    "titre": "Introduction à l'IA",
                    "domaine": "IA",
                    "objectifs": ["Comprendre les concepts", "Pratiquer"],
                    "public_cible": "Développeurs juniors",
                    "duree_jours": 2,
                },
                "session_info": {
                    "id": 1,
                    "client": "Ministère de l'Éducation",
                    "client_id": 1,
                    "formateur": "M. RANAIVOSOA S.",
                },
                "options": {
                    "nb_participants": 20,
                    "type_formateur": "senior",
                    "type_salle": "standard",
                    "tva_applicable": True,
                },
            }
        }


class RegenerateRequest(BaseModel):
    """Corps de la requête pour régénérer une offre rejetée."""
    review_id: str = Field(..., description="ID du review rejeté")
    feedback: str = Field(..., min_length=10, description="Feedback humain détaillé")


# =============================================================================
# SCHÉMAS — RÉPONSES
# =============================================================================

class RouteResponse(BaseModel):
    """Réponse standardisée pour les routes M3."""
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

@router.get("/health", summary="[M3] État des agents IA Offres")
async def health_check() -> Dict[str, Any]:
    """Retourne l'état du module M3."""
    _log_request("GET", "/ia/offres/health")
    try:
        from app.services.offres import get_package_status
        status_data = get_package_status()
        return {"success": True, **status_data}
    except Exception as e:
        _handle_exception(e, "health_check")
        return {"success": False}


# =============================================================================
# ROUTE 1 — POST /generer-technique  (Agent M3-1 uniquement)
# =============================================================================

@router.post(
    "/generer-technique",
    response_model=RouteResponse,
    summary="[M3] Agent M3-1 — Générer uniquement l'offre technique",
)
async def generer_technique(
    payload: GenerateTechniqueRequest,
    orchestrator: OffreOrchestrator = Depends(get_offre_orchestrator),
) -> RouteResponse:
    """Génère l'offre technique via l'Agent M3-1."""
    _log_request(
        "POST", "/ia/offres/generer-technique",
        TDR=payload.tdr_data.get("titre", "N/A"),
        Client=payload.session_info.get("client", "N/A"),
    )
    start = time.perf_counter()
    try:
        result = await orchestrator.generate_technique(
            tdr_data=payload.tdr_data,
            session_info=payload.session_info,
        )
        elapsed = round(time.perf_counter() - start, 2)
        vlog(f"✅ [Route M3] generer-technique OK en {elapsed}s")
        return _build_response(result, "Offre technique générée.", elapsed)
    except Exception as e:
        _handle_exception(e, "generer_technique")
        return RouteResponse(success=False, message="")


# =============================================================================
# ROUTE 2 — POST /generer-financiere  (Agent M3-2 uniquement)
# =============================================================================

@router.post(
    "/generer-financiere",
    response_model=RouteResponse,
    summary="[M3] Agent M3-2 — Générer uniquement l'offre financière",
)
async def generer_financiere(
    payload: GenerateFinanciereRequest,
    orchestrator: OffreOrchestrator = Depends(get_offre_orchestrator),
) -> RouteResponse:
    """Génère l'offre financière via l'Agent M3-2."""
    _log_request(
        "POST", "/ia/offres/generer-financiere",
        Offre_TECH=payload.offre_technique.get("reference", "N/A"),
    )
    start = time.perf_counter()
    try:
        result = await orchestrator.generate_financiere(
            offre_technique=payload.offre_technique,
            options=payload.options,
        )
        elapsed = round(time.perf_counter() - start, 2)
        vlog(f"✅ [Route M3] generer-financiere OK en {elapsed}s")
        return _build_response(result, "Offre financière générée.", elapsed)
    except Exception as e:
        _handle_exception(e, "generer_financiere")
        return RouteResponse(success=False, message="")


# =============================================================================
# ROUTE 3 — POST /generer-complet  ( ROUTE PRINCIPALE)
# =============================================================================

@router.post(
    "/generer-complet",
    response_model=RouteResponse,
    summary=" [M3] Générer une offre complète (technique + financière + HITL)",
    description=(
        "Route principale du module M3.\n\n"
        "1. Génère l'offre technique (Agent M3-1)\n"
        "2. Génère l'offre financière (Agent M3-2)\n"
        "3. Crée un review HITL global (validation humaine obligatoire)\n\n"
        "⚠️ La validation humaine doit approuver avant envoi client."
    ),
)
async def generer_complet(
    payload: GenerateCompleteRequest,
    orchestrator: OffreOrchestrator = Depends(get_offre_orchestrator),
) -> RouteResponse:
    """Génère une offre complète (technique + financière)."""
    _log_request(
        "POST", "/ia/offres/generer-complet",
        TDR=payload.tdr_data.get("titre", "N/A"),
        Client=payload.session_info.get("client", "N/A"),
        Participants=payload.options.get("nb_participants", 20),
    )
    start = time.perf_counter()
    try:
        result = await orchestrator.generate_complete(
            tdr_data=payload.tdr_data,
            session_info=payload.session_info,
            options=payload.options,
        )
        elapsed = round(time.perf_counter() - start, 2)
        vlog(f"✅ [Route M3] generer-complet OK en {elapsed}s")
        return _build_response(result, "Offre complète générée.", elapsed)
    except Exception as e:
        _handle_exception(e, "generer_complet")
        return RouteResponse(success=False, message="")


# =============================================================================
# ROUTE 4 — POST /regenerer  (Régénération avec feedback)
# =============================================================================

@router.post(
    "/regenerer",
    response_model=RouteResponse,
    summary="[M3] Régénérer une offre rejetée avec feedback",
    description=(
        "Régénère une offre après rejet HITL.\n\n"
        "Le review_id doit correspondre à un review en statut 'rejected'."
    ),
)
async def regenerer(
    payload: RegenerateRequest,
    orchestrator: OffreOrchestrator = Depends(get_offre_orchestrator),
) -> RouteResponse:
    """Régénère une offre avec feedback humain."""
    _log_request(
        "POST", "/ia/offres/regenerer",
        Review_ID=payload.review_id,
        Feedback=payload.feedback[:80],
    )
    start = time.perf_counter()
    try:
        result = await orchestrator.regenerate(
            review_id=payload.review_id,
            feedback=payload.feedback,
        )
        elapsed = round(time.perf_counter() - start, 2)
        vlog(f"✅ [Route M3] regenerer OK en {elapsed}s")
        return _build_response(result, "Offre régénérée.", elapsed)
    except Exception as e:
        _handle_exception(e, "regenerer")
        return RouteResponse(success=False, message="")