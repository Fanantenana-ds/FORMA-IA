# app/api/v1/endpoints/rh_ia.py
# ============================================================
# ROUTES IA — M4 (Assistance RH — bonus)
# ============================================================
# 6 routes :
#   GET  /ia/rh/health
#   POST /ia/rh/preselection            — A1 : Présélection CV
#   POST /ia/rh/entretien/compte-rendu  — A2 : CR Entretien
#   POST /ia/rh/email/brouillon         — A3 : Email RH
#   POST /ia/rh/contrat-formateur       — A4 : Contrat formateur
#   POST /ia/rh/formateur/evaluer       — A5 : Évaluation post-session
# ============================================================

import os
import time
import logging
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.orchestrator.rh_orchestrator import RhOrchestrator, get_rh_orchestrator
from app.schemas.rh_ia import (
    PreselectionCvRequest,
    EntretienCrRequest,
    EmailRhRequest,
    ContratFormateurRequest,
    EvaluationFormateurRequest,
)

logger = logging.getLogger(__name__)
VERBOSE = os.getenv("VERBOSE_LOGS", "true").lower() == "true"


def vlog(msg: str, level: str = "info") -> None:
    if VERBOSE:
        getattr(logger, level)(msg)


router = APIRouter(
    prefix="/ia/rh",
    tags=["M4 — IA Assistance RH (bonus)"],
)


# =============================================================================
# HELPERS
# =============================================================================

class RouteResponse(BaseModel):
    success: bool
    message: str
    duration_seconds: Optional[float] = None
    review_id: Optional[str] = None
    review_status: Optional[str] = None
    requires_human_action: bool = False
    data: Optional[Dict[str, Any]] = None


def _handle_exception(e: Exception, context: str) -> None:
    if isinstance(e, ValueError):
        raise HTTPException(status_code=422, detail=f"Données invalides : {e}")
    if isinstance(e, RuntimeError):
        logger.error(f"❌ [Route M4] {context} — service : {e}")
        raise HTTPException(status_code=503, detail=str(e))
    logger.exception(f"💥 [Route M4] {context} : {e}")
    raise HTTPException(status_code=500, detail=f"Erreur interne : {type(e).__name__} — {e}")


def _build_hitl_response(result: Dict[str, Any], msg_ok: str, elapsed: float) -> RouteResponse:
    review_id = result.get("_review_id")
    status = result.get("_review_status", "pending_review")
    requires = status == "pending_review"
    message = msg_ok
    if requires:
        message += f" ⚠️ En attente validation (review={review_id})."
    return RouteResponse(
        success=True,
        message=message,
        duration_seconds=elapsed,
        review_id=review_id,
        review_status=status,
        requires_human_action=requires,
        data=result,
    )


# =============================================================================
# ROUTE 0 — GET /health
# =============================================================================

@router.get("/health", summary="[M4] État du module Assistance RH")
async def health_check() -> Dict[str, Any]:
    return {"success": True, "module": "M4 — Assistance RH", "agents": 5}


# =============================================================================
# ROUTE 1 — POST /preselection  (A1)
# =============================================================================

@router.post(
    "/preselection",
    response_model=RouteResponse,
    summary="[M4-A1] Présélectionner un profil formateur sur CV",
    description=(
        "Analyse un CV texte + critères de poste et produit une fiche de "
        "présélection structurée (score, décision, questions d'entretien).\n\n"
        "⚠️ Résultat soumis à validation HITL avant archivage."
    ),
)
async def preselectionner_cv(
    payload: PreselectionCvRequest,
    orchestrator: RhOrchestrator = Depends(get_rh_orchestrator),
) -> RouteResponse:
    start = time.perf_counter()
    try:
        result = await orchestrator.preselectionner_cv(
            cv_texte=payload.cv_texte,
            criteres_poste=payload.criteres_poste,
        )
        elapsed = round(time.perf_counter() - start, 2)
        return _build_hitl_response(result, "Fiche de présélection générée.", elapsed)
    except Exception as e:
        _handle_exception(e, "preselectionner_cv")
        return RouteResponse(success=False, message="")


# =============================================================================
# ROUTE 2 — POST /entretien/compte-rendu  (A2)
# =============================================================================

@router.post(
    "/entretien/compte-rendu",
    response_model=RouteResponse,
    summary="[M4-A2] Rédiger un compte-rendu d'entretien",
    description=(
        "À partir de notes brutes, génère un CR structuré avec décision "
        "(RECRUTER / APPROFONDIR / NE_PAS_RECRUTER).\n\n"
        "⚠️ Résultat soumis à validation HITL avant archivage."
    ),
)
async def rediger_cr_entretien(
    payload: EntretienCrRequest,
    orchestrator: RhOrchestrator = Depends(get_rh_orchestrator),
) -> RouteResponse:
    start = time.perf_counter()
    try:
        result = await orchestrator.rediger_cr_entretien(
            notes_brutes=payload.notes_brutes,
            candidat=payload.candidat,
            poste=payload.poste,
            interviewers=payload.interviewers,
            date_entretien=payload.date_entretien,
        )
        elapsed = round(time.perf_counter() - start, 2)
        return _build_hitl_response(result, "Compte-rendu d'entretien rédigé.", elapsed)
    except Exception as e:
        _handle_exception(e, "rediger_cr_entretien")
        return RouteResponse(success=False, message="")


# =============================================================================
# ROUTE 3 — POST /email/brouillon  (A3)
# =============================================================================

@router.post(
    "/email/brouillon",
    response_model=RouteResponse,
    summary="[M4-A3] Rédiger un brouillon d'email RH",
    description=(
        "Génère un email RH professionnel (acceptation, refus, convocation, "
        "proposition de mission, demande d'info).\n\n"
        "⚠️ Email soumis à validation HITL avant envoi — jamais envoyé automatiquement."
    ),
)
async def rediger_email_rh(
    payload: EmailRhRequest,
    orchestrator: RhOrchestrator = Depends(get_rh_orchestrator),
) -> RouteResponse:
    start = time.perf_counter()
    try:
        result = await orchestrator.rediger_email_rh(
            type_email=payload.type_email,
            destinataire=payload.destinataire,
            contexte=payload.contexte,
        )
        elapsed = round(time.perf_counter() - start, 2)
        return _build_hitl_response(result, "Brouillon d'email rédigé.", elapsed)
    except Exception as e:
        _handle_exception(e, "rediger_email_rh")
        return RouteResponse(success=False, message="")


# =============================================================================
# ROUTE 4 — POST /contrat-formateur  (A4)
# =============================================================================

@router.post(
    "/contrat-formateur",
    response_model=RouteResponse,
    summary="[M4-A4] Générer un contrat de prestation formateur",
    description=(
        "Génère un contrat de prestation complet (texte_complet prêt à imprimer) "
        "à partir des données formateur et de la session.\n\n"
        "Liaison M3 : les données formateur et session proviennent de la Préparation.\n\n"
        "⚠️ Contrat soumis à validation HITL avant signature et envoi."
    ),
)
async def generer_contrat_formateur(
    payload: ContratFormateurRequest,
    orchestrator: RhOrchestrator = Depends(get_rh_orchestrator),
) -> RouteResponse:
    start = time.perf_counter()
    try:
        result = await orchestrator.generer_contrat_formateur(
            formateur=payload.formateur.model_dump(),
            session=payload.session.model_dump(),
        )
        elapsed = round(time.perf_counter() - start, 2)
        nom = payload.formateur.nom
        return _build_hitl_response(result, f"Contrat formateur généré pour {nom}.", elapsed)
    except Exception as e:
        _handle_exception(e, "generer_contrat_formateur")
        return RouteResponse(success=False, message="")


# =============================================================================
# ROUTE 5 — POST /formateur/evaluer  (A5)
# =============================================================================

@router.post(
    "/formateur/evaluer",
    response_model=RouteResponse,
    summary="[M4-A5] Évaluer un formateur post-session (données M5)",
    description=(
        "Agrège les résultats M5 (satisfaction, présences, rapport) pour "
        "produire une fiche d'évaluation interne du formateur.\n\n"
        "Liaison M5 : passer les résultats des agents M5 dans `donnees_session`.\n\n"
        "Document interne — pas de HITL requis (non diffusé sans décision explicite)."
    ),
)
async def evaluer_formateur(
    payload: EvaluationFormateurRequest,
    orchestrator: RhOrchestrator = Depends(get_rh_orchestrator),
) -> RouteResponse:
    start = time.perf_counter()
    try:
        result = await orchestrator.evaluer_formateur(
            formateur=payload.formateur,
            session=payload.session,
            donnees_session=payload.donnees_session.model_dump(),
        )
        elapsed = round(time.perf_counter() - start, 2)
        score = result.get("score_global", "N/A")
        recommandation = result.get("recommandation", "N/A")
        return RouteResponse(
            success=True,
            message=f"Évaluation formateur terminée — Score : {score} — {recommandation}.",
            duration_seconds=elapsed,
            requires_human_action=False,
            data=result,
        )
    except Exception as e:
        _handle_exception(e, "evaluer_formateur")
        return RouteResponse(success=False, message="")
