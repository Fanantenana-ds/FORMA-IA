import logging
import os
import time
from typing import Any, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from app.api.v1.endpoints._helpers import build_response as _build_resp
from app.api.v1.endpoints._helpers import handle_exception as _handle_exc
from app.api.v1.endpoints._helpers import log_request as _log_req
from app.orchestrator.formation_orchestrator import (
    FormationOrchestrator,
    get_formation_orchestrator,
)
from app.schemas.common import RouteResponse
from app.services.hitl import approve_review as _approve
from app.services.hitl import get_review as _get
from app.services.hitl import get_stats, list_pending
from app.services.hitl import reject_review as _reject
from app.utils.security import verify_api_key

logger = logging.getLogger(__name__)

VERBOSE = os.getenv("VERBOSE_LOGS", "true").lower() == "true"


def vlog(msg: str, level: str = "info") -> None:
    if VERBOSE:
        getattr(logger, level)(msg)


# =============================================================================
# ROUTER
# =============================================================================
router = APIRouter(
    prefix="/ia/formations",
    tags=["M5 — IA Formations"],
    dependencies=[Depends(verify_api_key)],
)


# =============================================================================
# HELPERS
# =============================================================================

def _log_request(method: str, path: str, **kwargs) -> None:
    _log_req(logger, "Route IA", method, path, **kwargs)


def _handle_exception(e: Exception, context: str) -> None:
    _handle_exc(e, context, "Route IA", logger)


def _build_response(result: dict[str, Any], msg_ok: str, elapsed: float) -> "RouteResponse":
    """Construit une réponse uniforme avec info HITL."""
    review_id = result.get("_review_id") if isinstance(result, dict) else None
    status = result.get("_review_status") if isinstance(result, dict) else None

    requires_action = status == "pending_review"
    message = msg_ok
    if requires_action:
        message += f" ⚠️ En attente validation (review={review_id})."

    return RouteResponse(
        success=True,
        message=message,
        duration_seconds=elapsed,
        review_id=review_id,
        review_status=status,
        requires_human_action=requires_action,
        data=result,
    )


# =============================================================================
# SCHÉMAS — REQUÊTES
# =============================================================================

class GenerateFormsRequest(BaseModel):
    titre: str = Field(..., min_length=3)
    domaine: str
    niveau_cible: str
    date_debut: str
    date_fin: str
    lieu: str
    formateur: str
    max_participants: int = Field(..., ge=1, le=500)
    public_cible: str | None = None
    supports_resume: str | None = Field(None, max_length=5000)


class RegenerateFormsRequest(BaseModel):
    session_info: dict[str, Any]
    previous_generation: dict[str, Any]
    feedback: str = Field(..., min_length=10)


class AnalyzeLevelsRequest(BaseModel):
    session_info: dict[str, Any]
    participants: list[dict[str, Any]]
    corrige: dict[str, str]


class AnalyzeSatisfactionRequest(BaseModel):
    session_info: dict[str, Any]
    responses: list[dict[str, Any]]


class AnalyzePresencesRequest(BaseModel):
    session_info: dict[str, Any]
    participants: list[dict[str, Any]]
    presences: list[dict[str, Any]]


class GenerateAttestationsRequest(BaseModel):
    session_data: dict[str, Any]
    eligible_participants: list[dict[str, Any]]


class GenerateReportRequest(BaseModel):
    session_data: dict[str, Any]


class ApproveReviewRequest(BaseModel):
    reviewer_note: str | None = Field(None, max_length=1000)


class RejectReviewRequest(BaseModel):
    reason: str = Field(..., min_length=3, max_length=1000)


# =============================================================================
# SCHÉMAS — RÉPONSES
# =============================================================================

class RouteResponse(BaseModel):
    success: bool
    message: str
    duration_seconds: float | None = None
    review_id: str | None = None
    review_status: str | None = None
    requires_human_action: bool = False
    data: dict[str, Any] | None = None


class ReviewResponse(BaseModel):
    success: bool
    message: str
    review: dict[str, Any] | None = None


# =============================================================================
# ROUTE 0 — GET /health
# =============================================================================

@router.get("/health", summary="[M5] État des agents IA")
async def health_check() -> dict[str, Any]:
    _log_request("GET", "/ia/formations/health")
    try:
        from app.services.formations import get_package_status
        return {"success": True, **get_package_status()}
    except Exception as e:
        _handle_exception(e, "health_check")
        return {"success": False}

@router.post("/generate-forms", response_model=RouteResponse,
             summary="[M5] Agent 1 — Générer les 4 formulaires")
async def generate_forms(
    payload: GenerateFormsRequest,
    orchestrator: FormationOrchestrator = Depends(get_formation_orchestrator),
) -> RouteResponse:
    _log_request("POST", "/ia/formations/generate-forms",
                 Titre=payload.titre, Domaine=payload.domaine)
    start = time.perf_counter()
    try:
        result = await orchestrator.generate_forms(payload.model_dump(exclude_none=True))
        elapsed = round(time.perf_counter() - start, 2)
        vlog(f"✅ [Route IA] generate-forms OK en {elapsed}s")
        return _build_response(result, "Formulaires générés.", elapsed)
    except Exception as e:
        _handle_exception(e, "generate_forms")
        return RouteResponse(success=False, message="")


@router.post("/regenerate-forms", response_model=RouteResponse,
             summary="[M5] Agent 1 — Régénérer avec feedback")
async def regenerate_forms(
    payload: RegenerateFormsRequest,
    orchestrator: FormationOrchestrator = Depends(get_formation_orchestrator),
) -> RouteResponse:
    _log_request("POST", "/ia/formations/regenerate-forms",
                 Titre=payload.session_info.get("titre", "N/A"),
                 Feedback=payload.feedback[:80])
    start = time.perf_counter()
    try:
        result = await orchestrator.regenerate_forms(
            payload.session_info, payload.previous_generation, payload.feedback
        )
        elapsed = round(time.perf_counter() - start, 2)
        vlog(f"✅ [Route IA] regenerate-forms OK en {elapsed}s")
        return _build_response(result, "Formulaires régénérés.", elapsed)
    except Exception as e:
        _handle_exception(e, "regenerate_forms")
        return RouteResponse(success=False, message="")



@router.post("/analyze-levels", response_model=RouteResponse,
             summary="[M5] Agent 2 — Analyser les niveaux")
async def analyze_levels(
    payload: AnalyzeLevelsRequest,
    orchestrator: FormationOrchestrator = Depends(get_formation_orchestrator),
) -> RouteResponse:
    _log_request("POST", "/ia/formations/analyze-levels",
                 Session=payload.session_info.get("titre", "N/A"),
                 Participants=len(payload.participants))
    start = time.perf_counter()
    try:
        result = await orchestrator.analyze_levels(
            payload.session_info, payload.participants, payload.corrige
        )
        elapsed = round(time.perf_counter() - start, 2)
        vlog(f"✅ [Route IA] analyze-levels OK en {elapsed}s")
        return _build_response(result, "Analyse niveaux réussie.", elapsed)
    except Exception as e:
        _handle_exception(e, "analyze_levels")
        return RouteResponse(success=False, message="")


@router.post("/analyze-satisfaction", response_model=RouteResponse,
             summary="[M5] Agent 3 — Analyser la satisfaction")
async def analyze_satisfaction(
    payload: AnalyzeSatisfactionRequest,
    orchestrator: FormationOrchestrator = Depends(get_formation_orchestrator),
) -> RouteResponse:
    _log_request("POST", "/ia/formations/analyze-satisfaction",
                 Session=payload.session_info.get("titre", "N/A"),
                 Réponses=len(payload.responses))
    start = time.perf_counter()
    try:
        result = await orchestrator.analyze_satisfaction(
            payload.session_info, payload.responses
        )
        elapsed = round(time.perf_counter() - start, 2)
        vlog(f"✅ [Route IA] analyze-satisfaction OK en {elapsed}s")
        return _build_response(result, "Analyse satisfaction réussie.", elapsed)
    except Exception as e:
        _handle_exception(e, "analyze_satisfaction")
        return RouteResponse(success=False, message="")


@router.post("/analyze-presences", response_model=RouteResponse,
             summary="[M5] Agent 4 — Analyser les présences")
async def analyze_presences(
    payload: AnalyzePresencesRequest,
    orchestrator: FormationOrchestrator = Depends(get_formation_orchestrator),
) -> RouteResponse:
    _log_request("POST", "/ia/formations/analyze-presences",
                 Session=payload.session_info.get("titre", "N/A"),
                 Participants=len(payload.participants),
                 Présences=len(payload.presences))
    start = time.perf_counter()
    try:
        result = await orchestrator.analyze_presences(
            payload.session_info, payload.participants, payload.presences
        )
        elapsed = round(time.perf_counter() - start, 2)
        vlog(f"✅ [Route IA] analyze-presences OK en {elapsed}s")
        return _build_response(result, "Analyse présences réussie.", elapsed)
    except Exception as e:
        _handle_exception(e, "analyze_presences")
        return RouteResponse(success=False, message="")


@router.post("/generate-attestations", response_model=RouteResponse,
             summary="[M5] Agent 5 — Générer les attestations")
async def generate_attestations(
    payload: GenerateAttestationsRequest,
    orchestrator: FormationOrchestrator = Depends(get_formation_orchestrator),
) -> RouteResponse:
    _log_request("POST", "/ia/formations/generate-attestations",
                 Session=payload.session_data.get("titre", "N/A"),
                 Éligibles=len(payload.eligible_participants))
    start = time.perf_counter()
    try:
        result = await orchestrator.generate_attestations(
            payload.session_data, payload.eligible_participants
        )
        elapsed = round(time.perf_counter() - start, 2)
        vlog(f"✅ [Route IA] generate-attestations OK en {elapsed}s")
        return _build_response(result, "Attestations générées.", elapsed)
    except Exception as e:
        _handle_exception(e, "generate_attestations")
        return RouteResponse(success=False, message="")


@router.post("/generate-report", response_model=RouteResponse,
             summary="[M5] Agent 6 — Générer le rapport final")
async def generate_report(
    payload: GenerateReportRequest,
    orchestrator: FormationOrchestrator = Depends(get_formation_orchestrator),
) -> RouteResponse:
    _log_request("POST", "/ia/formations/generate-report",
                 Session=payload.session_data.get("titre", "N/A"),
                 Participants=payload.session_data.get("total_inscrits", 0))
    start = time.perf_counter()
    try:
        result = await orchestrator.generate_report(payload.session_data)
        elapsed = round(time.perf_counter() - start, 2)
        vlog(f"✅ [Route IA] generate-report OK en {elapsed}s")
        return _build_response(result, "Rapport final généré.", elapsed)
    except Exception as e:
        _handle_exception(e, "generate_report")
        return RouteResponse(success=False, message="")


@router.get("/agents", summary="[M5] Liste des agents IA")
async def list_agents(
    orchestrator: FormationOrchestrator = Depends(get_formation_orchestrator),
) -> dict[str, Any]:
    _log_request("GET", "/ia/formations/agents")
    agents = {
        "Agent 1 — FormGenerator":        orchestrator.form_generator is not None,
        "Agent 2 — LevelAnalyzer":        orchestrator.level_analyzer is not None,
        "Agent 3 — SatisfactionAnalyzer": orchestrator.satisfaction_analyzer is not None,
        "Agent 4 — PresenceAnalyzer":     orchestrator.presence_analyzer is not None,
        "Agent 5 — AttestationGenerator": orchestrator.attestation_generator is not None,
        "Agent 6 — ReportGenerator":      orchestrator.report_generator is not None,
        "Agent 7 — KnowledgeBase (V2)":   orchestrator.knowledge_base is not None,
    }
    active = sum(1 for v in agents.values() if v)
    return {
        "success": True,
        "module": "M5",
        "active_count": active,
        "total": len(agents),
        "agents": agents,
    }


@router.get("/pending-reviews",
            summary="[HITL] Liste des contenus en attente de validation")
async def list_pending_reviews(
    agent_id: str | None = Query(None),
    criticity: str | None = Query(None),
) -> dict[str, Any]:
    _log_request("GET", "/ia/formations/pending-reviews",
                 Agent=agent_id or "tous", Criticité=criticity or "toutes")
    try:
        
        reviews = list_pending(agent_id=agent_id, criticity=criticity)
        vlog(f"✅ [HITL] {len(reviews)} contenu(s) en attente")
        return {
            "success": True,
            "total": len(reviews),
            "filters": {"agent_id": agent_id, "criticity": criticity},
            "reviews": reviews,
        }
    except Exception as e:
        _handle_exception(e, "list_pending_reviews")
        return {"success": False, "reviews": []}



@router.get("/reviews/stats",
            summary="[HITL] Statistiques des validations")
async def get_reviews_stats() -> dict[str, Any]:
    _log_request("GET", "/ia/formations/reviews/stats")
    try:
       
        stats = get_stats()
        vlog(
            f"✅ [HITL] Stats : pending={stats.get('pending', 0)}, "
            f"approved={stats.get('approved', 0)}, "
            f"rejected={stats.get('rejected', 0)}"
        )
        return {"success": True, "stats": stats}
    except Exception as e:
        _handle_exception(e, "get_reviews_stats")
        return {"success": False, "stats": {}}


@router.get("/reviews/{review_id}",
            summary="[HITL] Détails d'un contenu en attente")
async def get_review(review_id: str) -> dict[str, Any]:
    _log_request("GET", f"/ia/formations/reviews/{review_id}")
    try:
       
        review = _get(review_id)
        if not review:
            raise HTTPException(404, detail=f"Review '{review_id}' non trouvée")
        vlog(f"✅ [HITL] Review récupérée : {review_id}")
        return {"success": True, "review": review}
    except HTTPException:
        raise
    except Exception as e:
        _handle_exception(e, "get_review")
        return {"success": False, "review": None}


@router.post("/reviews/{review_id}/approve",
             response_model=ReviewResponse,
             summary="[HITL] Approuver un contenu")
async def approve_review(
    review_id: str,
    payload: ApproveReviewRequest,
) -> ReviewResponse:
    _log_request("POST", f"/ia/formations/reviews/{review_id}/approve",
                 Note=payload.reviewer_note or "Aucune")
    try:
        
        review = _approve(review_id=review_id, reviewer_note=payload.reviewer_note)
        if not review:
            raise HTTPException(404, detail=f"Review '{review_id}' non trouvée")
        vlog(f"✅ [HITL] Review approuvée : {review_id}")
        return ReviewResponse(
            success=True,
            message=f"Contenu '{review_id}' approuvé.",
            review=review,
        )
    except HTTPException:
        raise
    except Exception as e:
        _handle_exception(e, "approve_review")
        return ReviewResponse(success=False, message="")

@router.post("/reviews/{review_id}/reject",
             response_model=ReviewResponse,
             summary="[HITL] Rejeter un contenu")
async def reject_review(
    review_id: str,
    payload: RejectReviewRequest,
) -> ReviewResponse:
    _log_request("POST", f"/ia/formations/reviews/{review_id}/reject",
                 Raison=payload.reason)
    try:

        review = _reject(review_id=review_id, reason=payload.reason)
        if not review:
            raise HTTPException(404, detail=f"Review '{review_id}' non trouvée")
        vlog(f"✅ [HITL] Review rejetée : {review_id}")
        return ReviewResponse(
            success=True,
            message=f"Contenu '{review_id}' rejeté.",
            review=review,
        )
    except HTTPException:
        raise
    except Exception as e:
        _handle_exception(e, "reject_review")
        return ReviewResponse(success=False, message="")


# =============================================================================
# PUBLICATION GOOGLE FORMS (après approbation HITL)
# =============================================================================

class PublishFormsRequest(BaseModel):
    session_titre: str = Field(default="Formation", description="Titre de la session")


class PublishFormsResponse(BaseModel):
    success: bool
    message: str
    forms_urls: dict[str, str] = {}
    forms_count: int = 0


@router.post(
    "/reviews/{review_id}/publish-forms",
    response_model=PublishFormsResponse,
    summary="[Google Forms] Publier les formulaires approuvés sur Google Forms",
    description=(
        "Après approbation HITL d'un review `agent_1_forms`, "
        "crée les 4 formulaires sur Google Forms et retourne leurs URLs."
    ),
)
async def publish_forms(
    review_id: str,
    payload: PublishFormsRequest,
) -> PublishFormsResponse:
    _log_request("POST", f"/ia/formations/reviews/{review_id}/publish-forms",
                 session_titre=payload.session_titre)
    try:
        from app.services.formations.google_forms_publisher_service import (
            GoogleFormsPublisherService,
        )

        # 1. Vérifier que la review existe et est approuvée
        review = _get(review_id)
        if not review:
            raise HTTPException(404, detail=f"Review '{review_id}' non trouvée")
        if review.get("status") != "approved":
            raise HTTPException(
                422,
                detail=(
                    f"Review '{review_id}' non approuvée "
                    f"(statut actuel : {review.get('status')}). "
                    "Approuve d'abord via POST /reviews/{id}/approve."
                ),
            )
        if review.get("agent_id") != "agent_1_forms":
            raise HTTPException(
                422,
                detail=(
                    f"Cette route ne concerne que agent_1_forms. "
                    f"Agent reçu : {review.get('agent_id')}"
                ),
            )

        # 2. Vérifier que le service est disponible
        if not GoogleFormsPublisherService.is_available():
            raise HTTPException(
                503,
                detail=(
                    "GOOGLE_REFRESH_TOKEN absent. "
                    "Lance scripts/setup_google_oauth.py pour configurer."
                ),
            )

        # 3. Publier les formulaires
        publisher = GoogleFormsPublisherService()
        forms_data = review.get("data", {})
        forms_urls = await publisher.publish_all(
            forms_data=forms_data,
            session_titre=payload.session_titre,
        )

        vlog(f"✅ [GoogleForms] {len(forms_urls)} formulaires publiés pour {review_id}")
        return PublishFormsResponse(
            success=True,
            message=f"{len(forms_urls)} formulaire(s) créé(s) sur Google Forms.",
            forms_urls=forms_urls,
            forms_count=len(forms_urls),
        )

    except HTTPException:
        raise
    except Exception as e:
        _handle_exception(e, "publish_forms")
        return PublishFormsResponse(success=False, message=str(e))


# =============================================================================
# ROUTE — POST /creer-formulaires  (Google Forms réels après HITL)
# =============================================================================

class CreerFormulaireRequest(BaseModel):
    review_id: str = Field(..., description="ID du review APPROUVÉ (agent_1_forms)")
    session_title: str = Field(default="", description="Titre de la session (préfixe des formulaires)")


@router.post(
    "/creer-formulaires",
    response_model=RouteResponse,
    summary="[M5] Créer les 4 Google Forms réels depuis le JSON HITL approuvé",
    description=(
        "Appelle l'API Google Forms v1 pour créer les 4 formulaires réels "
        "(inscription, test_avant, test_apres, satisfaction).\n\n"
        "⚠️ Refusé si le review n'est pas **approuvé** — aucun formulaire Google "
        "n'est créé sans validation humaine du contenu IA.\n\n"
        "Nécessite GOOGLE_CREDENTIALS_PATH défini dans .env et l'API Google Forms "
        "activée sur le projet GCP."
    ),
)
async def creer_formulaires(
    payload: CreerFormulaireRequest,
    orchestrator: FormationOrchestrator = Depends(get_formation_orchestrator),
) -> RouteResponse:
    """Crée les 4 Google Forms réels après approbation HITL."""
    _log_request(
        "POST", "/ia/formations/creer-formulaires",
        Review_ID=payload.review_id,
        Session=payload.session_title or "N/A",
    )
    start = time.perf_counter()
    try:
        result = await orchestrator.creer_formulaires_google(
            review_id=payload.review_id,
            session_title=payload.session_title,
        )
        elapsed = round(time.perf_counter() - start, 2)
        n = result.get("total_created", 0)
        success = result.get("success", False)
        message = f"{n} formulaire(s) Google créé(s)." if success else "Création partielle."
        vlog(f"✅ [Route M5] creer-formulaires terminé en {elapsed}s : {message}")
        return RouteResponse(
            success=success,
            message=message,
            duration_seconds=elapsed,
            review_id=payload.review_id,
            data=result,
        )
    except Exception as e:
        _handle_exception(e, "creer_formulaires")
        return RouteResponse(success=False, message="")


# =============================================================================
# ROUTE — POST /sync-responses  (Récupération réponses Google Forms)
# =============================================================================

class SyncResponsesRequest(BaseModel):
    review_id: str = Field(
        ...,
        description="ID de la review agent_1_forms contenant les form_id Google",
    )
    sections: Optional[list[str]] = Field(
        default=None,
        description=(
            "Sections à récupérer : inscription, test_avant, test_apres, satisfaction. "
            "Absent → toutes les sections."
        ),
    )


@router.post(
    "/sync-responses",
    response_model=RouteResponse,
    summary="[M5] Récupérer les réponses des formulaires Google Forms",
    description=(
        "Appelle l'API Google Forms v1 pour récupérer les réponses des participants "
        "aux 4 formulaires créés lors de `/creer-formulaires`.\n\n"
        "**Pré-requis :** la route `/creer-formulaires` doit avoir été appelée "
        "pour cette review (les form_id sont stockés automatiquement).\n\n"
        "**Réponses retournées :** structurées par section "
        "(inscription / test_avant / test_apres / satisfaction), prêtes à passer "
        "directement aux agents 2 (analyze-levels), 3 (analyze-satisfaction) et "
        "4 (analyze-presences).\n\n"
        "Nécessite GOOGLE_CREDENTIALS_PATH défini dans .env."
    ),
)
async def sync_responses(
    payload: SyncResponsesRequest,
    orchestrator: FormationOrchestrator = Depends(get_formation_orchestrator),
) -> RouteResponse:
    """Récupère les réponses Google Forms et les retourne structurées."""
    _log_request(
        "POST", "/ia/formations/sync-responses",
        Review_ID=payload.review_id,
        Sections=payload.sections or "toutes",
    )
    start = time.perf_counter()
    try:
        result = await orchestrator.sync_responses(
            review_id=payload.review_id,
            sections=payload.sections,
        )
        elapsed = round(time.perf_counter() - start, 2)
        total = result.get("total_responses", 0)
        vlog(f"✅ [Route M5] sync-responses OK en {elapsed}s — {total} réponse(s)")
        return RouteResponse(
            success=True,
            message=f"{total} réponse(s) récupérée(s) depuis Google Forms.",
            duration_seconds=elapsed,
            review_id=payload.review_id,
            data=result,
        )
    except Exception as e:
        _handle_exception(e, "sync_responses")
        return RouteResponse(success=False, message="")


# =============================================================================
# SYNC BACKEND — Présences (après approbation HITL A4)
# =============================================================================

class SyncPresencesRequest(BaseModel):
    review_id: str = Field(..., description="ID du review APPROUVÉ (agent_4_presences)")
    seance_id: str = Field(..., description="UUID Backend de la séance")
    force: bool = False


@router.post(
    "/synchroniser/presences",
    response_model=RouteResponse,
    summary="[M5] Sync A4 → Backend POST /sessions/seances/{id}/presences",
    description=(
        "Enregistre les présences validées côté Backend.\n\n"
        "⚠️ Requiert une review HITL approuvée (agent_4_presences)."
    ),
)
async def synchroniser_presences(
    payload: SyncPresencesRequest,
    orchestrator: FormationOrchestrator = Depends(get_formation_orchestrator),
) -> RouteResponse:
    start = time.perf_counter()
    try:
        result = await orchestrator.synchroniser_presences(
            review_id=payload.review_id,
            seance_id=payload.seance_id,
            force=payload.force,
        )
        elapsed = round(time.perf_counter() - start, 2)
        sent = (result.get("backend_sync") or result).get("sent", False)
        return RouteResponse(
            success=True,
            message="Présences enregistrées côté Backend." if sent else "Déjà synchronisé.",
            duration_seconds=elapsed,
            review_id=payload.review_id,
            data=result,
        )
    except Exception as e:
        _handle_exception(e, "synchroniser_presences")
        return RouteResponse(success=False, message="")


# =============================================================================
# SYNC BACKEND — Attestations (après approbation HITL A5)
# =============================================================================

class SyncAttestationsRequest(BaseModel):
    review_id: str = Field(..., description="ID du review APPROUVÉ (agent_5_attestations)")
    session_id: str = Field(..., description="UUID Backend de la session")
    force: bool = False


@router.post(
    "/synchroniser/attestations",
    response_model=RouteResponse,
    summary="[M5] Sync A5 → Backend POST /documents/attestations/{session_id}",
    description=(
        "Demande au Backend de créer les attestations de la session.\n\n"
        "⚠️ Requiert une review HITL approuvée (agent_5_attestations) — "
        "attestations jamais créées sans validation humaine."
    ),
)
async def synchroniser_attestations(
    payload: SyncAttestationsRequest,
    orchestrator: FormationOrchestrator = Depends(get_formation_orchestrator),
) -> RouteResponse:
    start = time.perf_counter()
    try:
        result = await orchestrator.synchroniser_attestations(
            review_id=payload.review_id,
            session_id=payload.session_id,
            force=payload.force,
        )
        elapsed = round(time.perf_counter() - start, 2)
        sent = (result.get("backend_sync") or result).get("sent", False)
        count = (result.get("backend_sync") or result).get("count", 0)
        return RouteResponse(
            success=True,
            message=f"{count} attestation(s) créée(s) côté Backend." if sent else "Déjà synchronisé.",
            duration_seconds=elapsed,
            review_id=payload.review_id,
            data=result,
        )
    except Exception as e:
        _handle_exception(e, "synchroniser_attestations")
        return RouteResponse(success=False, message="")
