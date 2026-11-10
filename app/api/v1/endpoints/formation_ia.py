import logging
import os
import time
import uuid
import zipfile
from datetime import datetime
from io import BytesIO
from pathlib import Path
from typing import Any, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

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
from app.services.hitl import get_stats, list_pending, list_reviews
from app.services.hitl import replace_pending_review_data
from app.services.hitl import reject_review as _reject
from app.services.hitl import delete_pending_review as _delete_pending
from app.services.hitl import delete_review as _delete_any
from app.core.dependencies import get_current_tenant_user, require_role
from app.database import get_db
from app.models.formation import Inscription, Participant, Presence, Seance, Session as TrainingSession, StatutPresence
from app.models.rh import Formateur
from app.services.formations.attestation_generator_service import AttestationGeneratorService
from app.services.formations.presence_analyzer_service import SEUIL_ELIGIBILITE_ATTESTATION
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
    session_id: str = Field(..., min_length=1, max_length=100,
                            description="Identifiant unique de la session Backend")
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


class AttestationEditRequest(BaseModel):
    content: dict[str, Any]
    expected_updated_at: str = Field(..., min_length=1, max_length=80)


class AttestationDeleteRequest(BaseModel):
    expected_updated_at: str = Field(..., min_length=1, max_length=80)


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
        # Conserve le lien M5 → M4 dans les métadonnées HITL quand la session
        # est animée par un formateur connu. Le lien n'est jamais déduit du texte.
        formateur_id = payload.session_info.get("formateur_id")
        if formateur_id and result.get("_review_id"):
            from app.services.hitl import patch_review
            patch_review(result["_review_id"], {
                "formateur_id": str(formateur_id),
                "formateur_nom": payload.session_info.get("formateur_nom"),
                "session_id": payload.session_info.get("session_id"),
                "session_title": payload.session_info.get("titre"),
                "taux_presence": payload.session_info.get("taux_presence"),
            })
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
    current_user=Depends(require_role("DIRECTION", "ADMIN", "ASSISTANT")),
    db: Session = Depends(get_db),
    orchestrator: FormationOrchestrator = Depends(get_formation_orchestrator),
) -> RouteResponse:
    session_id = payload.session_data.get("id") or payload.session_data.get("session_id")
    if not session_id:
        raise HTTPException(status_code=422, detail="Identifiant de session obligatoire.")
    session_data, _, eligible_participants, incomplete = _attestation_session_data(str(session_id), current_user, db)
    if incomplete:
        raise HTTPException(status_code=409, detail="Complétez tous les pointages avant de générer les attestations.")
    _log_request("POST", "/ia/formations/generate-attestations",
                 Session=session_data.get("titre", "N/A"),
                 Éligibles=len(eligible_participants))
    start = time.perf_counter()
    try:
        result = await orchestrator.generate_attestations(
            session_data, eligible_participants
        )
        elapsed = round(time.perf_counter() - start, 2)
        vlog(f"✅ [Route IA] generate-attestations OK en {elapsed}s")
        return _build_response(result, "Attestations générées.", elapsed)
    except Exception as e:
        _handle_exception(e, "generate_attestations")
        return RouteResponse(success=False, message="")


def _attestation_session_data(
    session_id: str,
    current_user: Any,
    db: Session,
) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]], int]:
    """Lit les inscriptions et présences réelles sous le tenant authentifié."""
    try:
        session_uuid = uuid.UUID(session_id)
    except (ValueError, TypeError) as exc:
        raise HTTPException(status_code=422, detail="Identifiant de session invalide.") from exc

    owner_id = current_user.owner_id or current_user.id
    session = db.query(TrainingSession).filter(
        TrainingSession.id == session_uuid,
        TrainingSession.owner_id == owner_id,
    ).first()
    if session is None:
        raise HTTPException(status_code=404, detail="Session introuvable dans votre espace.")

    seances = db.query(Seance).filter(
        Seance.session_id == session.id,
        Seance.owner_id == owner_id,
    ).order_by(Seance.date, Seance.heure_debut).all()
    if not seances:
        raise HTTPException(status_code=409, detail="Ajoutez au moins une séance avant d’évaluer l’éligibilité.")

    inscriptions = db.query(Inscription).filter(
        Inscription.session_id == session.id,
        Inscription.owner_id == owner_id,
    ).all()
    participant_ids = [item.participant_id for item in inscriptions]
    participants_db = db.query(Participant).filter(
        Participant.id.in_(participant_ids), Participant.owner_id == owner_id,
    ).all() if participant_ids else []
    participant_by_id = {str(item.id): item for item in participants_db}

    seance_ids = [item.id for item in seances]
    presences = db.query(Presence).filter(
        Presence.seance_id.in_(seance_ids), Presence.owner_id == owner_id,
    ).all()
    presence_by_pair = {
        (str(item.seance_id), str(item.participant_id)): item
        for item in presences
    }

    rows: list[dict[str, Any]] = []
    eligible: list[dict[str, Any]] = []
    incomplete = 0
    for inscription in inscriptions:
        participant = participant_by_id.get(str(inscription.participant_id))
        if participant is None:
            continue
        marked = [
            presence_by_pair.get((str(seance.id), str(participant.id)))
            for seance in seances
        ]
        missing = sum(item is None for item in marked)
        incomplete += missing
        present_count = sum(
            item is not None and item.statut in {StatutPresence.PRESENT, StatutPresence.RETARD}
            for item in marked
        )
        rate = round(present_count / len(seances) * 100, 1)
        is_eligible = missing == 0 and rate >= SEUIL_ELIGIBILITE_ATTESTATION
        name = " ".join(part for part in (participant.prenom, participant.nom) if part)
        row = {
            "id": str(participant.id),
            "nom": name,
            "email": participant.email,
            "entreprise": participant.entreprise,
            "nb_presences": present_count,
            "nb_seances": len(seances),
            "taux_presence": rate,
            "eligible_attestation": is_eligible,
            "pointages_manquants": missing,
        }
        rows.append(row)
        if is_eligible:
            eligible.append(row)

    trainer = db.query(Formateur).filter(
        Formateur.id == session.formateur_id,
        Formateur.owner_id == owner_id,
    ).first() if session.formateur_id else None
    themes = list(dict.fromkeys(item.theme for item in seances if item.theme))
    duration_hours = 0.0
    for seance in seances:
        try:
            start = datetime.strptime(seance.heure_debut, "%H:%M")
            end = datetime.strptime(seance.heure_fin, "%H:%M")
            hours = (end - start).total_seconds() / 3600
            if 0 < hours <= 16:
                duration_hours += hours
        except (TypeError, ValueError):
            continue
    session_info = {
        "id": str(session.id),
        "session_id": str(session.id),
        "titre": session.titre,
        "domaine": session.formation_code or "Formation",
        "formation_code": session.formation_code,
        "date_debut": session.date_debut.isoformat() if session.date_debut else "",
        "date_fin": session.date_fin.isoformat() if session.date_fin else "",
        "lieu": session.lieu or "À préciser",
        "formateur": " ".join(part for part in (trainer.prenom, trainer.nom) if part) if trainer else "À préciser",
        "formateur_id": str(session.formateur_id) if session.formateur_id else None,
        "duree_jours": len({item.date for item in seances}),
        "duree_heures": round(duration_hours, 1) if duration_hours else None,
        "themes": themes,
        "require_grounded_competencies": True,
    }
    return session_info, rows, eligible, incomplete


@router.get("/sessions/{session_id}/attestations/eligibilite", summary="[M6] Vérifier l'éligibilité à partir des présences enregistrées")
async def verifier_eligibilite_attestations(
    session_id: str,
    current_user=Depends(require_role("DIRECTION", "ADMIN", "ASSISTANT")),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    session_info, participants, eligible, incomplete = _attestation_session_data(session_id, current_user, db)
    return {
        "success": True,
        "session": session_info,
        "seuil_presence": SEUIL_ELIGIBILITE_ATTESTATION,
        "pointages_complets": incomplete == 0,
        "pointages_manquants": incomplete,
        "total_participants": len(participants),
        "total_eligible": len(eligible),
        "participants": participants,
    }


def _review_has_generated_attestation_pdf(review: dict[str, Any]) -> bool:
    """Un review vide ou dont les PDF ont disparu ne doit pas bloquer un nouvel essai."""
    output_dir = AttestationGeneratorService.OUTPUT_DIR.resolve()
    for item in (review.get("data") or {}).get("attestations", []):
        try:
            path = Path(str(item.get("pdf_path") or "")).resolve()
            if path.suffix.lower() == ".pdf" and output_dir in path.parents and path.is_file():
                return True
        except (OSError, RuntimeError):
            continue
    return False


@router.post("/sessions/{session_id}/attestations/generer", summary="[M6] Générer les attestations PDF des participants éligibles")
async def generer_attestations_session(
    session_id: str,
    current_user=Depends(require_role("DIRECTION", "ADMIN", "ASSISTANT")),
    db: Session = Depends(get_db),
    orchestrator: FormationOrchestrator = Depends(get_formation_orchestrator),
) -> dict[str, Any]:
    session_info, participants, eligible, incomplete = _attestation_session_data(session_id, current_user, db)
    if incomplete:
        raise HTTPException(
            status_code=409,
            detail=f"Complétez les {incomplete} pointage(s) manquant(s) avant la génération. Aucun pointage absent n'est supposé.",
        )
    if not participants:
        raise HTTPException(status_code=409, detail="Aucun participant inscrit à cette session.")
    if session_info.get("lieu") == "À préciser" or session_info.get("formateur") == "À préciser":
        raise HTTPException(status_code=409, detail="Renseignez le lieu et le formateur de la session avant la génération.")
    if not eligible:
        return {"success": True, "message": "Aucun participant n'atteint le seuil de 75 %.", "data": {"total_eligible": 0, "attestations": []}}
    for pending in list_pending(agent_id="agent_5_attestations"):
        existing = _get(pending.get("review_id", "")) or {}
        if (str((existing.get("meta") or {}).get("session_id")) == str(session_id)
                and _review_has_generated_attestation_pdf(existing)):
            raise HTTPException(status_code=409, detail="Un lot d'attestations attend déjà sa validation pour cette session.")
    for existing_item in list_reviews(status="approved", agent_id="agent_5_attestations"):
        existing = _get(existing_item.get("review_id", "")) or {}
        if (str((existing.get("meta") or {}).get("session_id")) == str(session_id)
                and _review_has_generated_attestation_pdf(existing)):
            raise HTTPException(status_code=409, detail="Des attestations ont déjà été approuvées pour cette session.")

    result = await orchestrator.generate_attestations(session_info, eligible)
    response_message = (
        "Aucun PDF n'a pu être généré. Consultez les erreurs par participant et relancez la préparation."
        if not result.get("total_pdf_generated")
        else "Attestations générées pour validation humaine."
    )
    return _build_response(result, response_message, float(result.get("duration_seconds", 0)))


def _attestation_review(review_id: str, numero: str, *, approved_only: bool = False) -> tuple[dict[str, Any], dict[str, Any]]:
    review = _get(review_id)
    if not review or review.get("agent_id") != "agent_5_attestations":
        raise HTTPException(status_code=404, detail="Dossier d'attestations introuvable.")
    data = review.get("data") or {}
    attestation = next((item for item in data.get("attestations", []) if item.get("numero_unique") == numero), None)
    if not attestation:
        raise HTTPException(status_code=404, detail="Attestation introuvable dans ce dossier.")
    if approved_only and attestation.get("approval_status") != "approved":
        raise HTTPException(status_code=403, detail="Le téléchargement est disponible après approbation humaine.")
    path = Path(str(attestation.get("pdf_path") or "")).resolve()
    output_dir = AttestationGeneratorService.OUTPUT_DIR.resolve()
    if output_dir not in path.parents or path.suffix.lower() != ".pdf" or not path.is_file():
        raise HTTPException(status_code=404, detail="Fichier PDF indisponible.")
    return review, attestation


@router.get("/reviews/{review_id}/attestations/{numero}/preview", summary="[M6] Prévisualiser un PDF en attente de validation")
async def preview_attestation(review_id: str, numero: str, _current_user=Depends(require_role("DIRECTION", "ADMIN", "ASSISTANT"))):
    _, item = _attestation_review(review_id, numero)
    return FileResponse(item["pdf_path"], media_type="application/pdf", headers={"Content-Disposition": "inline"})


@router.get("/reviews/{review_id}/attestations/{numero}/download", summary="[M6] Télécharger un PDF approuvé")
async def telecharger_attestation(review_id: str, numero: str, _current_user=Depends(require_role("DIRECTION", "ADMIN", "ASSISTANT"))):
    _, item = _attestation_review(review_id, numero, approved_only=True)
    return FileResponse(item["pdf_path"], media_type="application/pdf", filename=f"{numero}.pdf")


@router.put("/reviews/{review_id}/attestations/{numero}", summary="[M6] Modifier une attestation en attente et régénérer son PDF")
async def modifier_attestation(
    review_id: str,
    numero: str,
    payload: AttestationEditRequest,
    _current_user=Depends(require_role("DIRECTION", "ADMIN", "ASSISTANT")),
):
    review, item = _attestation_review(review_id, numero)
    if review.get("status") != "pending_review" or item.get("approval_status") == "approved":
        raise HTTPException(status_code=409, detail="Une attestation approuvée ne peut plus être modifiée.")
    if review.get("updated_at") != payload.expected_updated_at:
        raise HTTPException(status_code=409, detail="Le lot a changé. Rechargez-le avant de modifier l’attestation.")
    original = item.get("content") or {}
    edited = payload.content
    if set(edited) != set(original) or not isinstance(edited.get("details"), dict):
        raise HTTPException(status_code=422, detail="Conservez la structure complète de l’attestation.")
    if set(edited["details"]) != set(original.get("details") or {}):
        raise HTTPException(status_code=422, detail="Conservez tous les champs descriptifs de l’attestation.")
    minimum_competencies = 0 if (item.get("metadata") or {}).get("competencies_source") == "participation_only" else 3
    if not isinstance(edited.get("competences"), list) or not minimum_competencies <= len(edited["competences"]) <= 12:
        if minimum_competencies:
            raise HTTPException(status_code=422, detail="L’attestation doit contenir de 3 à 12 compétences vérifiables.")
        raise HTTPException(status_code=422, detail="L’attestation de participation peut rester sans compétence ; 12 compétences maximum.")
    text_values = [value for key, value in edited.items() if key not in {"details", "competences"}]
    text_values.extend(edited["details"].values())
    text_values.extend(edited["competences"])
    if any(not isinstance(value, str) or len(value) > 1200 for value in text_values):
        raise HTTPException(status_code=422, detail="Chaque champ de l’attestation doit être un texte de 1 200 caractères maximum.")

    output_dir = AttestationGeneratorService.OUTPUT_DIR.resolve()
    new_path = output_dir / f"attestation_revision_{uuid.uuid4().hex}.pdf"
    generator = AttestationGeneratorService.__new__(AttestationGeneratorService)
    revised_item = {**item, "content": edited, "pdf_path": str(new_path), "pdf_generated": True}
    generated_path = generator._build_attestation_pdf(revised_item, item.get("participant") or {}, output_path=new_path)
    if not generated_path or not Path(generated_path).is_file():
        raise HTTPException(status_code=500, detail="Le nouveau PDF n’a pas pu être généré ; l’attestation reste inchangée.")
    data = dict(review.get("data") or {})
    data["attestations"] = [revised_item if row.get("numero_unique") == numero else row for row in data.get("attestations", [])]
    try:
        updated = replace_pending_review_data(review_id, data, ("agent_5_attestations",), payload.expected_updated_at)
    except (KeyError, PermissionError, ValueError, RuntimeError) as exc:
        Path(generated_path).unlink(missing_ok=True)
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return {"success": True, "review": updated}


@router.delete("/reviews/{review_id}/attestations/{numero}", summary="[M6] Supprimer une attestation individuelle avant validation")
async def supprimer_attestation(
    review_id: str,
    numero: str,
    payload: AttestationDeleteRequest,
    _current_user=Depends(require_role("DIRECTION", "ADMIN", "ASSISTANT")),
):
    review, item = _attestation_review(review_id, numero)
    if review.get("status") != "pending_review" or item.get("approval_status") == "approved":
        raise HTTPException(status_code=409, detail="Une attestation approuvée ne peut plus être supprimée.")
    if review.get("updated_at") != payload.expected_updated_at:
        raise HTTPException(status_code=409, detail="Le lot a changé. Rechargez-le avant de supprimer l’attestation.")
    data = dict(review.get("data") or {})
    items = list(data.get("attestations") or [])
    if len(items) <= 1:
        raise HTTPException(status_code=409, detail="La dernière attestation ne peut pas être retirée seule. Supprimez le lot en attente depuis l’Espace IA.")
    data["attestations"] = [row for row in items if row.get("numero_unique") != numero]
    try:
        updated = replace_pending_review_data(review_id, data, ("agent_5_attestations",), payload.expected_updated_at)
    except (KeyError, PermissionError, ValueError, RuntimeError) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    old_path = Path(str(item.get("pdf_path") or "")).resolve()
    if AttestationGeneratorService.OUTPUT_DIR.resolve() in old_path.parents and old_path.suffix.lower() == ".pdf":
        old_path.unlink(missing_ok=True)
    return {"success": True, "review": updated}


@router.post("/reviews/{review_id}/attestations/{numero}/approve", summary="[M6] Approuver une attestation dans le lot")
async def approuver_attestation(review_id: str, numero: str, payload: ApproveReviewRequest, _current_user=Depends(require_role("DIRECTION", "ADMIN", "ASSISTANT"))):
    review = _get(review_id)
    if not review or review.get("agent_id") != "agent_5_attestations":
        raise HTTPException(status_code=404, detail="Dossier d'attestations introuvable.")
    if review.get("status") != "pending_review":
        raise HTTPException(status_code=409, detail="Ce lot a déjà été traité.")
    data = dict(review.get("data") or {})
    items = list(data.get("attestations") or [])
    target = next((item for item in items if item.get("numero_unique") == numero), None)
    if not target:
        raise HTTPException(status_code=404, detail="Attestation introuvable dans ce lot.")
    target["approval_status"] = "approved"
    target["reviewer_note"] = payload.reviewer_note
    data["attestations"] = items
    replace_pending_review_data(review_id, data, ("agent_5_attestations",), review.get("updated_at", ""))
    all_approved = all(item.get("approval_status") == "approved" for item in items)
    if all_approved:
        approved = _approve(review_id=review_id, reviewer_note="Toutes les attestations du lot ont été approuvées.")
        return {"success": True, "lot_approved": True, "review": approved}
    return {"success": True, "lot_approved": False, "approved_count": sum(item.get("approval_status") == "approved" for item in items)}


@router.get("/reviews/{review_id}/attestations.zip", summary="[M6] Télécharger le lot d'attestations approuvé en ZIP")
async def telecharger_lot_attestations(review_id: str, _current_user=Depends(require_role("DIRECTION", "ADMIN", "ASSISTANT"))):
    review = _get(review_id)
    if not review or review.get("agent_id") != "agent_5_attestations":
        raise HTTPException(status_code=404, detail="Dossier d'attestations introuvable.")
    if review.get("status") != "approved":
        raise HTTPException(status_code=403, detail="Le lot ZIP est disponible après approbation de toutes les attestations.")
    archive = BytesIO()
    with zipfile.ZipFile(archive, mode="w", compression=zipfile.ZIP_DEFLATED) as zip_file:
        count = 0
        for item in (review.get("data") or {}).get("attestations", []):
            _, approved_item = _attestation_review(review_id, item.get("numero_unique", ""), approved_only=True)
            zip_file.write(approved_item["pdf_path"], arcname=f"{approved_item['numero_unique']}.pdf")
            count += 1
    if not count:
        raise HTTPException(status_code=404, detail="Aucun PDF disponible dans ce lot.")
    archive.seek(0)
    return StreamingResponse(archive, media_type="application/zip", headers={"Content-Disposition": f'attachment; filename="attestations-{review_id}.zip"'})


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


@router.get("/reviews", summary="[HITL] Historique des contenus approuvés ou rejetés")
async def list_review_history(
    status: str = Query("approved", pattern="^(approved|rejected)$"),
    agent_id: str | None = Query(None),
) -> dict[str, Any]:
    reviews = list_reviews(status=status, agent_id=agent_id)
    return {"success": True, "status": status, "total": len(reviews), "reviews": reviews}


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


class ManualDocumentEditRequest(BaseModel):
    content: dict[str, Any] = Field(..., min_length=1)
    expected_updated_at: str = Field(..., min_length=1)


@router.patch("/reviews/{review_id}/document", summary="Modifier un TDR ou une offre avant validation humaine")
async def modifier_document_en_attente(
    review_id: str,
    payload: ManualDocumentEditRequest,
    _current_user=Depends(require_role("DIRECTION", "ADMIN", "ASSISTANT")),
) -> dict[str, Any]:
    from app.services.tdr.tdr_document_generator import TDRDocumentGenerator

    review = _get(review_id)
    if not review:
        raise HTTPException(404, detail="Validation introuvable.")
    agent = review.get("agent_id")
    allowed = ("agent_m2_tdr", "agent_m3_technique", "agent_m3_financiere")
    if agent not in allowed:
        raise HTTPException(403, detail="La modification manuelle est réservée aux documents TDR et offres.")
    if review.get("status") != "pending_review":
        raise HTTPException(409, detail="Ce document a déjà été validé ou rejeté.")
    if review.get("updated_at") != payload.expected_updated_at:
        raise HTTPException(409, detail="Le document a changé. Rechargez-le avant de modifier.")
    if len(str(payload.content)) > 1_000_000:
        raise HTTPException(413, detail="Document trop volumineux.")

    original = review.get("data") or {}
    if agent == "agent_m2_tdr":
        previous_content = original.get("data") or {}
        if set(payload.content) != set(previous_content):
            raise HTTPException(422, detail="Conservez tous les champs du TDR lors de la modification.")
        client = (original.get("_inputs") or {}).get("brief", {}).get("client") or "Client"
        docx, pdf = TDRDocumentGenerator().generate(payload.content, client)
        if not docx or not pdf:
            raise HTTPException(500, detail="Impossible de produire les nouveaux fichiers Word et PDF du TDR. Le document reste inchangé.")
        revised = {**original, "data": payload.content, "files": {"docx": docx, "pdf": pdf}}
    else:
        protected = {"success", "metadata"}
        editable = {key for key in original if not key.startswith("_") and key not in protected}
        if set(payload.content) != editable:
            raise HTTPException(422, detail="Conservez tous les champs de l’offre lors de la modification.")
        revised = {**original, **payload.content}

    try:
        updated = replace_pending_review_data(review_id, revised, allowed, payload.expected_updated_at)
    except KeyError as exc:
        raise HTTPException(404, detail=str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(403, detail=str(exc)) from exc
    except (ValueError, RuntimeError) as exc:
        raise HTTPException(409, detail=str(exc)) from exc
    return {"success": True, "review": updated}


@router.delete("/reviews/{review_id}", summary="Supprimer une validation encore en attente")
async def delete_pending_review(review_id: str, _current_user=Depends(require_role("DIRECTION", "ADMIN", "ASSISTANT"))):
    result = _delete_pending(review_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Validation introuvable.")
    if result is False:
        raise HTTPException(status_code=409, detail="Cette validation a déjà été traitée et ne peut plus être supprimée.")
    return {"success": True, "message": "Validation en attente supprimée.", "review_id": review_id}


@router.delete("/history/{review_id}", summary="Supprimer définitivement une décision de l'historique")
async def delete_history_review(review_id: str, _current_user=Depends(require_role("DIRECTION", "ADMIN", "ASSISTANT"))):
    result = _delete_any(review_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Décision introuvable.")
    return {"success": True, "message": "Décision supprimée de l'historique.", "review_id": review_id}


@router.post("/reviews/{review_id}/approve",
             response_model=ReviewResponse,
             summary="[HITL] Approuver un contenu")
async def approve_review(
    review_id: str,
    payload: ApproveReviewRequest,
    _current_user=Depends(require_role("DIRECTION", "ADMIN", "ASSISTANT")),
) -> ReviewResponse:
    _log_request("POST", f"/ia/formations/reviews/{review_id}/approve",
                 Note=payload.reviewer_note or "Aucune")
    try:
        
        current = _get(review_id)
        if current and current.get("agent_id") == "agent_5_attestations":
            data = dict(current.get("data") or {})
            attestations = list(data.get("attestations") or [])
            for item in attestations:
                item["approval_status"] = "approved"
                item["reviewer_note"] = payload.reviewer_note
            data["attestations"] = attestations
            replace_pending_review_data(review_id, data, ("agent_5_attestations",), current.get("updated_at", ""))
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
    _current_user=Depends(require_role("DIRECTION", "ADMIN", "ASSISTANT")),
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
    session_id: str = Field(..., min_length=1, max_length=100,
                            description="Identifiant de la session associée à la review")
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
            session_id=payload.session_id,
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
    session_id: str = Field(..., min_length=1, max_length=100,
                            description="Identifiant de la session associée aux formulaires")
    sections: list[str] | None = Field(
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
            session_id=payload.session_id,
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
    session_id: str = Field(..., min_length=1, max_length=100,
                            description="UUID Backend de la session concernée")
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
            session_id=payload.session_id,
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


# =============================================================================
# ANALYSE DEPUIS DB — Niveaux et satisfaction via liens internes
# =============================================================================

@router.post(
    "/{session_id}/analyser-niveaux-db",
    response_model=RouteResponse,
    summary="[M5] Agent 2 — Analyser les niveaux depuis la DB (liens internes)",
    description=(
        "Lit les inscriptions avec scores de positionnement et test final "
        "directement depuis la DB (système /inscription-publique). "
        "Aucun CSV ni corrigé requis — les scores sont déjà calculés."
    ),
)
async def analyser_niveaux_db(
    session_id: str,
    orchestrator: FormationOrchestrator = Depends(get_formation_orchestrator),
) -> RouteResponse:
    import datetime as _dt
    from app.database import SessionLocal
    from app.models.formation import Inscription, Participant, Session as TrainingSession

    start = time.perf_counter()
    try:
        db = SessionLocal()
        try:
            session_obj = db.query(TrainingSession).filter(TrainingSession.id == session_id).first()
            if not session_obj:
                raise HTTPException(status_code=404, detail="Session introuvable")

            rows = (
                db.query(Inscription, Participant)
                .join(Participant, Participant.id == Inscription.participant_id)
                .filter(Inscription.session_id == session_id)
                .all()
            )
        finally:
            db.close()

        participants_avec_scores = []
        participants_incomplets = 0
        for insc, part in rows:
            if insc.score_positionnement is None or insc.score_test_final is None:
                participants_incomplets += 1
                continue
            participants_avec_scores.append({
                "id": str(insc.participant_id),
                "nom": f"{part.prenom or ''} {part.nom}".strip() or f"Participant {insc.participant_id}",
                "reponses_avant": insc.reponses_positionnement or {},
                "reponses_apres": insc.reponses_test_final or {},
                "score_avant": insc.score_positionnement,
                "score_apres": insc.score_test_final,
                "niveau_initial": insc.niveau_initial,
                "niveau_final": insc.niveau_final,
            })

        if not participants_avec_scores:
            return RouteResponse(
                success=False,
                message="Aucun participant ne dispose à la fois du score initial et du score final. "
                        "Vérifiez les réponses aux deux évaluations avant de relancer l'analyse.",
                duration_seconds=round(time.perf_counter() - start, 2),
            )

        session_info = {
            "id": session_id,
            "session_id": session_id,
            "titre": session_obj.titre,
            "formation_code": session_obj.formation_code if hasattr(session_obj, "formation_code") else "",
            "domaine": session_obj.domaine if hasattr(session_obj, "domaine") else "Formation",
        }
        result = await orchestrator.analyze_levels(
            session_info, participants_avec_scores, {}
        )
        if isinstance(result.get("metadata"), dict):
            result["metadata"]["participants_incomplets"] = participants_incomplets
        elapsed = round(time.perf_counter() - start, 2)
        vlog(f"✅ [Route IA] analyser-niveaux-db OK en {elapsed}s — {len(participants_avec_scores)} participant(s)")
        message = f"Analyse niveaux réussie ({len(participants_avec_scores)} participant(s) avec deux scores)."
        if participants_incomplets:
            message += f" {participants_incomplets} participant(s) écarté(s), score initial ou final manquant."
        return _build_response(result, message, elapsed)
    except HTTPException:
        raise
    except Exception as e:
        _handle_exception(e, "analyser_niveaux_db")
        return RouteResponse(success=False, message="")


@router.post(
    "/{session_id}/analyser-satisfaction-db",
    response_model=RouteResponse,
    summary="[M5] Agent 3 — Analyser la satisfaction depuis la DB (liens internes)",
    description=(
        "Lit les inscriptions avec réponses de satisfaction "
        "directement depuis la DB (système /inscription-publique). "
        "Aucun CSV requis — les données sont déjà enregistrées."
    ),
)
async def analyser_satisfaction_db(
    session_id: str,
    orchestrator: FormationOrchestrator = Depends(get_formation_orchestrator),
) -> RouteResponse:
    from app.database import SessionLocal
    from app.models.formation import Inscription, Participant, Session as TrainingSession, Formateur

    start = time.perf_counter()
    try:
        db = SessionLocal()
        try:
            session_obj = db.query(TrainingSession).filter(TrainingSession.id == session_id).first()
            if not session_obj:
                raise HTTPException(status_code=404, detail="Session introuvable")

            rows = (
                db.query(Inscription, Participant)
                .join(Participant, Participant.id == Inscription.participant_id)
                .filter(
                    Inscription.session_id == session_id,
                    Inscription.reponses_satisfaction.isnot(None),
                )
                .all()
            )
        finally:
            db.close()

        if not rows:
            return RouteResponse(
                success=False,
                message="Aucune réponse de satisfaction trouvée pour cette session. "
                        "Les participants doivent d'abord répondre via le lien post-formation.",
                duration_seconds=round(time.perf_counter() - start, 2),
            )

        responses = []
        for insc, part in rows:
            rep = insc.reponses_satisfaction or {}
            rep["_nom"] = f"{part.prenom or ''} {part.nom}".strip()
            rep["_score"] = insc.score_satisfaction
            responses.append(rep)

        session_info = {
            "session_id": session_id,
            "titre": session_obj.titre,
            "formation_code": session_obj.formation_code if hasattr(session_obj, "formation_code") else "",
            "domaine": session_obj.domaine if hasattr(session_obj, "domaine") else "Formation",
        }
        result = await orchestrator.analyze_satisfaction(session_info, responses)
        elapsed = round(time.perf_counter() - start, 2)
        vlog(f"✅ [Route IA] analyser-satisfaction-db OK en {elapsed}s — {len(responses)} réponse(s)")
        return _build_response(result, f"Analyse satisfaction réussie ({len(responses)} réponses).", elapsed)
    except HTTPException:
        raise
    except Exception as e:
        _handle_exception(e, "analyser_satisfaction_db")
        return RouteResponse(success=False, message="")
