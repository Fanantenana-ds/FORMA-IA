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

from fastapi import APIRouter, Depends, HTTPException, UploadFile
from pydantic import BaseModel, Field

from app.services.vocal.assistant_vocal_service import get_assistant_vocal_service
from app.services.veille.access_service import verify_api_key

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/ia/vocal",
    tags=["Vocal — Agent vocal FORMA-IA"],
    dependencies=[Depends(verify_api_key)],
)


@router.post("/transcrire", summary="Transcrire une courte dictée française")
async def transcrire_vocal(audio: UploadFile):
    from app.services.vocal.transcription_service import MAX_AUDIO_BYTES, transcribe_audio

    try:
        content = await audio.read(MAX_AUDIO_BYTES + 1)
        text = await transcribe_audio(content, audio.content_type or "")
        return {"texte": text, "provider": "groq", "language": "fr"}
    finally:
        await audio.close()


# ──────────────────────────────────────────────────────────────
# Schémas
# ──────────────────────────────────────────────────────────────

class CommandeVocaleRequest(BaseModel):
    texte: str = Field(..., min_length=1, max_length=500, description="Texte transcrit depuis la voix")
    formations_disponibles: list[str] = Field(
        default_factory=list,
        description="Liste des noms de formations disponibles (contexte optionnel)",
    )
    conversation_id: str | None = Field(
        None, description="Identifiant de la conversation RAG vocale précédente"
    )
    contexte_action: list[str] = Field(default_factory=list, max_length=8)
    ecran_actuel: str | None = Field(default=None, max_length=64)
    formation_code: str | None = Field(default=None, max_length=100)


class CommandeVocaleResponse(BaseModel):
    intention: str
    confiance: float
    parametres: dict[str, Any]
    parametres_manquants: list[str]
    reponse_vocale: str
    action_frontend: str | None
    prefill: dict[str, Any]
    duree_ms: int
    conversation_id: str | None = None
    sources: list[dict[str, Any]] = []
    suggestions: list[str] = []
    texte_affiche: str = ""
    texte_a_lire: str = ""
    etat: str = "pret_a_verifier"
    niveau_preuve: str = "non_applicable"
    execution_demandee: bool = False
    execution_plan: dict[str, Any] | None = None


class ExecutionVocaleRequest(BaseModel):
    """Demande d'exécution après confirmation explicite dans l'interface."""
    action: str = Field(..., min_length=1, max_length=80)
    confirmer: bool = Field(False, description="Confirmation explicite de l'utilisateur")
    session_info: dict[str, Any] = Field(default_factory=dict)
    payload: dict[str, Any] = Field(default_factory=dict)


class ExecutionVocaleResponse(BaseModel):
    success: bool
    action: str
    etat: str
    message: str
    data: dict[str, Any] | None = None


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
async def analyser_commande(req: CommandeVocaleRequest, principal=Depends(verify_api_key)) -> CommandeVocaleResponse:
    debut = time.time()
    logger.info("🎤 Commande vocale reçue : '%s'", req.texte[:80])

    try:
        result = await get_assistant_vocal_service().traiter(
            texte=req.texte,
            formations=req.formations_disponibles,
            conversation_id=req.conversation_id,
            **({"contexte_action": [text[:500] for text in req.contexte_action]} if req.contexte_action else {}),
            **({"owner": str(principal.id)} if getattr(principal, "id", None) is not None else {}),
            **({"ecran_actuel": req.ecran_actuel} if req.ecran_actuel else {}),
            **({"formation_code": req.formation_code} if req.formation_code else {}),
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
        reponse_vocale=result.get("texte_a_lire", result.get("reponse_vocale", "")),
        action_frontend=result.get("action_frontend"),
        prefill=result.get("prefill", {}),
        duree_ms=duree,
        conversation_id=result.get("conversation_id"),
        sources=result.get("sources", []),
        suggestions=result.get("suggestions", []),
        texte_affiche=result.get("texte_affiche", result.get("reponse_vocale", "")),
        texte_a_lire=result.get("texte_a_lire", result.get("reponse_vocale", "")),
        etat=result.get("etat", "pret_a_verifier"),
        niveau_preuve=result.get("niveau_preuve", "non_applicable"),
        execution_demandee=result.get("execution_demandee", False),
        execution_plan=result.get("execution_plan"),
    )


@router.post(
    "/executer",
    response_model=ExecutionVocaleResponse,
    summary="Exécuter une action vocale confirmée",
    description=(
        "Exécute une action métier préparée par /commande après confirmation "
        "explicite. Les contenus externes restent soumis au HITL."
    ),
)
async def executer_commande_vocale(
    req: ExecutionVocaleRequest,
    principal=Depends(verify_api_key),
) -> ExecutionVocaleResponse:
    if not req.confirmer:
        return ExecutionVocaleResponse(
            success=False, action=req.action, etat="confirmation_requise",
            message="Confirmez l'action dans l'interface avant de l'exécuter.",
        )

    action = req.action
    try:
        from app.services.vocal.prerequisite_service import verifier_action
        intention_for_check = action
        check_context = {
            "reponses_disponibles": bool(req.payload.get("responses")),
            "projet_id": req.payload.get("projet_info", {}).get("id")
            if isinstance(req.payload.get("projet_info"), dict) else None,
        }
        prerequis = verifier_action(
            intention_for_check,
            formation_code=req.session_info.get("formation_code") or req.payload.get("formation_code"),
            session_id=req.session_info.get("session_id") or req.payload.get("session_id"),
            contexte=check_context,
        )
        if not prerequis.ok:
            return ExecutionVocaleResponse(
                success=False, action=action, etat="prerequis_manquant",
                message=prerequis.message,
            )
        from app.orchestrator.formation_orchestrator import get_formation_orchestrator
        if action == "generer_formulaires":
            session_info = {**req.session_info, **req.payload}
            result = await get_formation_orchestrator().generate_forms(session_info)
        elif action == "analyser_niveaux":
            result = await get_formation_orchestrator().analyze_levels(
                req.session_info,
                req.payload.get("participants", []),
                req.payload.get("corrige", {}),
            )
        elif action == "analyser_satisfaction":
            result = await get_formation_orchestrator().analyze_satisfaction(
                req.session_info, req.payload.get("responses", [])
            )
        elif action == "analyser_presences":
            result = await get_formation_orchestrator().analyze_presences(
                req.session_info,
                req.payload.get("participants", []),
                req.payload.get("presences", []),
            )
        elif action == "generer_attestation":
            result = await get_formation_orchestrator().generate_attestations(
                req.session_info, req.payload.get("eligible_participants", [])
            )
        elif action == "preparer_formation":
            from app.orchestrator.preparation_orchestrator import get_preparation_orchestrator
            result = await get_preparation_orchestrator().generate_complete(
                offre_data=req.payload.get("offre_data", {}),
                projet_info=req.payload.get("projet_info", {}),
                ressources=req.payload.get("ressources", {}),
                options=req.payload.get("options", {}),
            )
        elif action == "relance_facture":
            from app.orchestrator.facturation_orchestrator import get_facturation_orchestrator
            result = await get_facturation_orchestrator().generer_relance(
                str(req.payload.get("facture_id", ""))
            )
        else:
            return ExecutionVocaleResponse(
                success=False, action=action, etat="action_inconnue",
                message="Cette action vocale n'est pas encore raccordée à un service métier.",
            )
        return ExecutionVocaleResponse(
            success=True, action=action,
            etat="en_attente_validation" if result.get("_review_status") == "pending_review" else "termine",
            message=(
                "Résultat généré et envoyé à la validation humaine."
                if result.get("_review_status") == "pending_review"
                else "Action exécutée et résultat vérifié."
            ),
            data=result,
        )
    except (ValueError, RuntimeError) as exc:
        logger.warning("Action vocale bloquée (%s) : %s", action, exc)
        return ExecutionVocaleResponse(
            success=False, action=action, etat="bloquee",
            message=str(exc),
        )
    except Exception:
        logger.exception("Erreur d'exécution vocale (%s)", action)
        return ExecutionVocaleResponse(
            success=False, action=action, etat="erreur",
            message="Le service métier n'a pas confirmé l'exécution. Aucun succès n'est annoncé.",
        )


@router.get(
    "/health",
    summary="Santé du service vocal",
)
async def health() -> dict:
    return {"status": "ok", "service": "agent_vocal_forma_ia"}
