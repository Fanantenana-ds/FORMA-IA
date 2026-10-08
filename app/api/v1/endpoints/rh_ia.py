# app/api/v1/endpoints/rh_ia.py
# ============================================================
# ROUTES IA — M4 (Assistance RH — bonus)
# ============================================================
# 14 routes :
#   GET  /ia/rh/health
#   POST /ia/rh/cv/extraire-texte              — Extraction texte CV (tous formats)
#   POST /ia/rh/cv/analyser                    — Upload CV → extraction → présélection A1 (pipeline complet)
#   POST /ia/rh/cv/postuler                    — Canal 1 : Formulaire web (nom + email + CV + poste_code)
#   GET  /ia/rh/postes                         — Liste des postes ouverts
#   GET  /ia/rh/email/traiter-candidatures     — Canal 2 : Traitement emails IMAP non lus
#   POST /ia/rh/preselection                   — A1 : Présélection CV
#   POST /ia/rh/entretien/compte-rendu         — A2 : CR Entretien
#   POST /ia/rh/email/brouillon                — A3 : Email RH
#   POST /ia/rh/contrat-formateur              — A4 : Contrat formateur
#   POST /ia/rh/formateur/evaluer              — A5 : Évaluation post-session
#   POST /ia/rh/synchroniser/candidat          — Sync A1 → Backend POST /rh/candidats
#   POST /ia/rh/synchroniser/entretien-cr      — Sync A2 → Backend POST /rh/candidats/{id}/entretiens
#   POST /ia/rh/synchroniser/evaluation        — Sync A5 → Backend PATCH /rh/formateurs/{id}
# ============================================================

import os
import time
import logging
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from pydantic import BaseModel
from app.schemas.common import RouteResponse
from app.api.v1.endpoints._helpers import handle_exception as _handle_exc, build_response as _build_resp

from app.orchestrator.rh_orchestrator import RhOrchestrator, get_rh_orchestrator
from app.schemas.rh_ia import (
    PreselectionCvRequest,
    EntretienCrRequest,
    EmailRhRequest,
    EmailEnvoiRequest,
    EmailBrouillonPatchRequest,
    ContratFormateurRequest,
    EvaluationFormateurRequest,
)
from app.utils.security import verify_api_key

logger = logging.getLogger(__name__)
VERBOSE = os.getenv("VERBOSE_LOGS", "true").lower() == "true"


def vlog(msg: str, level: str = "info") -> None:
    if VERBOSE:
        getattr(logger, level)(msg)


router = APIRouter(
    prefix="/ia/rh",
    tags=["M4 — IA Assistance RH (bonus)"],
    dependencies=[Depends(verify_api_key)],
)


# =============================================================================
# HELPERS
# =============================================================================

def _handle_exception(e: Exception, context: str) -> None:
    _handle_exc(e, context, "Route M4", logger)


def _build_hitl_response(result: Dict[str, Any], msg_ok: str, elapsed: float) -> RouteResponse:
    return _build_resp(result, msg_ok, elapsed)


# =============================================================================
# ROUTE 0 — GET /health
# =============================================================================

@router.get("/health", summary="[M4] État du module Assistance RH")
async def health_check() -> Dict[str, Any]:
    from app.services.rh import email_scheduler_service
    scheduler = email_scheduler_service.statut()
    return {
        "success": True,
        "module": "M4 — Assistance RH",
        "agents": 5,
        "email_scheduler": scheduler,
    }


# =============================================================================
# ROUTE 0b — POST /cv/extraire-texte
# =============================================================================

EXTENSIONS_AUTORISEES = {".pdf", ".docx", ".doc", ".jpg", ".jpeg", ".png",
                         ".bmp", ".tiff", ".webp", ".txt"}
TAILLE_MAX_BYTES = 10 * 1024 * 1024  # 10 Mo


@router.post(
    "/cv/extraire-texte",
    summary="[M4] Extraire le texte d'un CV (PDF, DOCX, image, TXT)",
    description=(
        "Reçoit un fichier CV et retourne le texte extrait prêt pour A1.\n\n"
        "Cascade : pymupdf4llm + pdfplumber → Tesseract OCR → Groq Vision.\n\n"
        "Formats supportés : PDF, DOCX, DOC, JPG, PNG, BMP, TIFF, WEBP, TXT.\n\n"
        "Taille max : 10 Mo."
    ),
)
async def extraire_texte_cv(
    fichier: UploadFile = File(..., description="Fichier CV à analyser"),
) -> Dict[str, Any]:
    from app.services.rh.cv_extractor_service import extraire_texte_cv as _extraire

    start = time.perf_counter()

    # Validation extension
    from pathlib import Path
    ext = Path(fichier.filename or "").suffix.lower()
    if ext not in EXTENSIONS_AUTORISEES:
        raise HTTPException(
            status_code=422,
            detail=f"Format '{ext}' non supporté. Formats acceptés : {', '.join(sorted(EXTENSIONS_AUTORISEES))}",
        )

    # Lecture contenu
    contenu = await fichier.read()
    if not contenu:
        raise HTTPException(status_code=422, detail="Fichier vide.")
    if len(contenu) > TAILLE_MAX_BYTES:
        raise HTTPException(status_code=422, detail="Fichier trop volumineux (max 10 Mo).")

    texte, methode, lisible = await _extraire(contenu, fichier.filename or "cv")
    elapsed = round(time.perf_counter() - start, 2)

    if not lisible:
        return {
            "success": False,
            "message": (
                "Le CV soumis est illisible ou trop peu informatif. "
                "Veuillez renvoyer le CV en PDF texte, Word (DOCX) ou image nette."
            ),
            "methode": methode,
            "duration_seconds": elapsed,
            "cv_texte": None,
        }

    return {
        "success": True,
        "message": f"Texte extrait avec succès via {methode}.",
        "methode": methode,
        "duration_seconds": elapsed,
        "cv_texte": texte,
        "nb_caracteres": len(texte),
    }


# =============================================================================
# ROUTE 0c — POST /cv/analyser  (pipeline complet : upload → extraction → A1)
# =============================================================================

@router.post(
    "/cv/analyser",
    response_model=RouteResponse,
    summary="[M4] Analyser un CV fichier → extraction + présélection A1 en une seule étape",
    description=(
        "Pipeline complet :\n"
        "1. Upload du fichier CV (PDF, DOCX, image, TXT)\n"
        "2. Extraction automatique du texte\n"
        "3. Présélection IA (A1) avec fiche structurée + review HITL\n\n"
        "Critères du poste passés en form-data JSON.\n\n"
        "⚠️ Résultat soumis à validation HITL avant archivage."
    ),
)
async def analyser_cv_fichier(
    fichier: UploadFile = File(..., description="Fichier CV (PDF, DOCX, image, TXT)"),
    criteres_poste: str = File(
        ...,
        description=(
            'Critères du poste en JSON. Exemple : '
            '{"domaine":"IA","competences":["Python"],"niveau":"expert","experience_formation_min":"2 ans"}'
        ),
    ),
    orchestrator: RhOrchestrator = Depends(get_rh_orchestrator),
) -> RouteResponse:
    import json
    from pathlib import Path
    from app.services.rh.cv_extractor_service import extraire_texte_cv as _extraire

    start = time.perf_counter()

    # Validation extension
    ext = Path(fichier.filename or "").suffix.lower()
    if ext not in EXTENSIONS_AUTORISEES:
        raise HTTPException(
            status_code=422,
            detail=f"Format '{ext}' non supporté. Formats acceptés : {', '.join(sorted(EXTENSIONS_AUTORISEES))}",
        )

    # Parsing critères
    try:
        criteres = json.loads(criteres_poste)
    except (json.JSONDecodeError, TypeError):
        raise HTTPException(status_code=422, detail="criteres_poste doit être un JSON valide.")

    # Lecture fichier
    contenu = await fichier.read()
    if not contenu:
        raise HTTPException(status_code=422, detail="Fichier vide.")
    if len(contenu) > TAILLE_MAX_BYTES:
        raise HTTPException(status_code=422, detail="Fichier trop volumineux (max 10 Mo).")

    # Étape 1 — Extraction texte
    texte, methode_extraction, lisible = await _extraire(contenu, fichier.filename or "cv")

    if not lisible:
        raise HTTPException(
            status_code=422,
            detail=(
                f"CV illisible après extraction ({methode_extraction}). "
                "Veuillez soumettre un CV en PDF texte, DOCX ou image nette."
            ),
        )

    vlog(f"📄 CV extrait via {methode_extraction} ({len(texte)} chars) → A1 présélection")

    # Étape 2 — Présélection A1
    try:
        result = await orchestrator.preselectionner_cv(
            cv_texte=texte,
            criteres_poste=criteres,
        )
    except Exception as e:
        _handle_exception(e, "analyser_cv_fichier / preselectionner_cv")
        return RouteResponse(success=False, message="Erreur lors de la présélection.")

    elapsed = round(time.perf_counter() - start, 2)

    # Enrichir le résultat avec les infos d'extraction
    result["_extraction"] = {
        "methode": methode_extraction,
        "nb_caracteres": len(texte),
        "fichier": fichier.filename,
    }

    return _build_hitl_response(
        result,
        f"CV analysé ({methode_extraction}, {len(texte)} chars) — fiche de présélection générée.",
        elapsed,
    )


# =============================================================================
# ROUTE 0d — GET /postes  (liste des postes ouverts)
# =============================================================================

@router.get(
    "/postes",
    summary="[M4] Lister les postes de formateur ouverts",
    description="Retourne les postes actifs avec leur code et titre. Utilisé par le formulaire de candidature.",
)
async def lister_postes() -> Dict[str, Any]:
    from app.services.rh.candidature_service import lister_postes_actifs
    postes = lister_postes_actifs()
    return {"success": True, "postes": postes, "total": len(postes)}


# =============================================================================
# ROUTE 0e — POST /cv/postuler  (Canal 1 : formulaire web)
# =============================================================================

@router.post(
    "/cv/postuler",
    response_model=RouteResponse,
    summary="[M4] Canal 1 — Formulaire web : soumettre une candidature formateur",
    description=(
        "Pipeline complet pour candidature depuis formulaire web :\n"
        "1. Reçoit nom + email + code poste + fichier CV\n"
        "2. Vérifie que le poste existe et est actif\n"
        "3. Extrait le texte du CV\n"
        "4. Lance la présélection A1\n"
        "5. Envoie un accusé de réception par email au candidat\n\n"
        "⚠️ Résultat soumis à validation HITL."
    ),
)
async def postuler_formulaire(
    nom: str = File(..., description="Nom complet du candidat"),
    email: str = File(..., description="Email du candidat"),
    poste_code: str = File(..., description="Code du poste (ex: formateur-ia)"),
    fichier: UploadFile = File(..., description="CV (PDF, DOCX, image, TXT)"),
    orchestrator: RhOrchestrator = Depends(get_rh_orchestrator),
) -> RouteResponse:
    import json
    from pathlib import Path
    from app.services.rh.cv_extractor_service import extraire_texte_cv as _extraire
    from app.services.rh.candidature_service import get_poste, envoyer_accuse_reception

    start = time.perf_counter()

    # Vérifier poste
    poste = get_poste(poste_code)
    if not poste:
        raise HTTPException(
            status_code=404,
            detail=f"Poste '{poste_code}' introuvable ou inactif. Consultez GET /ia/rh/postes.",
        )

    # Validation extension
    ext = Path(fichier.filename or "").suffix.lower()
    if ext not in EXTENSIONS_AUTORISEES:
        raise HTTPException(
            status_code=422,
            detail=f"Format '{ext}' non supporté. Formats acceptés : {', '.join(sorted(EXTENSIONS_AUTORISEES))}",
        )

    # Lecture fichier
    contenu = await fichier.read()
    if not contenu:
        raise HTTPException(status_code=422, detail="Fichier CV vide.")
    if len(contenu) > TAILLE_MAX_BYTES:
        raise HTTPException(status_code=422, detail="CV trop volumineux (max 10 Mo).")

    # Étape 1 — Extraction texte
    texte, methode_extraction, lisible = await _extraire(contenu, fichier.filename or "cv")
    if not lisible:
        raise HTTPException(
            status_code=422,
            detail="CV illisible. Veuillez soumettre un CV en PDF texte, DOCX ou image nette.",
        )

    vlog(f"📄 Candidature '{nom}' / poste '{poste_code}' — CV extrait via {methode_extraction}")

    # Étape 2 — Présélection A1
    try:
        result = await orchestrator.preselectionner_cv(
            cv_texte=texte,
            criteres_poste=poste["criteres"],
        )
    except Exception as e:
        _handle_exception(e, "postuler_formulaire / preselectionner_cv")
        return RouteResponse(success=False, message="Erreur lors de la présélection.")

    # Étape 3 — Accusé de réception email (non bloquant)
    await envoyer_accuse_reception(
        nom_candidat=nom,
        email_candidat=email,
        titre_poste=poste["titre"],
    )

    elapsed = round(time.perf_counter() - start, 2)

    result["_candidature"] = {
        "nom": nom,
        "email": email,
        "poste_code": poste_code,
        "titre_poste": poste["titre"],
        "methode_extraction": methode_extraction,
        "fichier": fichier.filename,
    }

    return _build_hitl_response(
        result,
        f"Candidature de {nom} pour '{poste['titre']}' analysée — en attente validation RH.",
        elapsed,
    )


# =============================================================================
# ROUTE 0f — GET /email/traiter-candidatures  (Canal 2 : IMAP)
# =============================================================================

@router.get(
    "/email/traiter-candidatures",
    summary="[M4] Canal 2 — Traiter les candidatures reçues par email (IMAP)",
    description=(
        "Lit les emails non lus de la boîte RH, extrait les CV en pièce jointe\n"
        "et lance automatiquement la présélection A1 pour chaque candidature.\n\n"
        "Déclenchement : manuel via cette route, ou planifié toutes les X minutes.\n\n"
        "Variables .env requises : IMAP_HOST, IMAP_PORT, IMAP_USER, IMAP_PASSWORD"
    ),
)
async def traiter_candidatures_email(
    orchestrator: RhOrchestrator = Depends(get_rh_orchestrator),
) -> Dict[str, Any]:
    import asyncio
    from app.services.rh.cv_extractor_service import extraire_texte_cv as _extraire
    from app.services.rh.candidature_service import (
        lire_candidatures_email, get_poste, envoyer_accuse_reception
    )

    start = time.perf_counter()
    vlog("📧 Traitement candidatures email IMAP...")

    candidatures = lire_candidatures_email()
    if not candidatures:
        return {
            "success": True,
            "message": "Aucune nouvelle candidature par email.",
            "traites": 0,
            "resultats": [],
        }

    resultats = []
    for c in candidatures:
        try:
            poste = get_poste(c["poste_code"])
            if not poste:
                resultats.append({
                    "nom": c["nom"], "email": c["email"],
                    "statut": "erreur", "detail": f"Poste '{c['poste_code']}' introuvable",
                })
                continue

            # Extraction CV
            texte, methode, lisible = await _extraire(c["fichier_contenu"], c["fichier_nom"])
            if not lisible:
                resultats.append({
                    "nom": c["nom"], "email": c["email"],
                    "statut": "cv_illisible", "detail": f"Extraction échouée ({methode})",
                })
                continue

            # Présélection A1
            result = await orchestrator.preselectionner_cv(
                cv_texte=texte,
                criteres_poste=poste["criteres"],
            )

            # Accusé de réception
            await envoyer_accuse_reception(
                nom_candidat=c["nom"],
                email_candidat=c["email"],
                titre_poste=poste["titre"],
            )

            resultats.append({
                "nom": c["nom"],
                "email": c["email"],
                "poste": poste["titre"],
                "statut": "analyse",
                "review_id": result.get("_review_id"),
                "score": result.get("score_global"),
                "decision": result.get("decision"),
            })

        except Exception as exc:
            logger.error(f"❌ Erreur traitement candidature {c.get('email')} : {exc}")
            resultats.append({
                "nom": c["nom"], "email": c["email"],
                "statut": "erreur", "detail": str(exc),
            })

    elapsed = round(time.perf_counter() - start, 2)
    traites = sum(1 for r in resultats if r["statut"] == "analyse")

    return {
        "success": True,
        "message": f"{traites}/{len(candidatures)} candidature(s) traitée(s) avec succès.",
        "traites": traites,
        "duration_seconds": elapsed,
        "resultats": resultats,
    }


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
            review_id_a1=payload.review_id_a1,
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
# ROUTE 3b — PATCH /email/brouillon/{review_id}  (modifier avant approbation)
# =============================================================================

@router.patch(
    "/email/brouillon/{review_id}",
    summary="[M4-A3] Modifier un brouillon d'email avant approbation HITL",
    description=(
        "Permet de corriger l'objet et/ou le corps d'un brouillon email **avant** "
        "de l'approuver et de l'envoyer.\n\n"
        "⚠️ Impossible de modifier un brouillon déjà approuvé ou déjà envoyé.\n\n"
        "Laissez `objet` ou `corps` vide pour ne pas modifier ce champ."
    ),
)
async def modifier_brouillon_email(
    review_id: str,
    payload: EmailBrouillonPatchRequest,
) -> Dict[str, Any]:
    from app.services.hitl import get_review, patch_review

    review = get_review(review_id)
    if not review:
        raise HTTPException(status_code=404, detail=f"Review '{review_id}' introuvable.")

    statut = review.get("status") or review.get("statut", "")
    if statut == "approved":
        raise HTTPException(
            status_code=422,
            detail=f"Review '{review_id}' déjà approuvé — impossible de modifier.",
        )

    meta = review.get("meta") or {}
    if meta.get("email_sent"):
        raise HTTPException(
            status_code=422,
            detail=f"Email déjà envoyé pour review '{review_id}' — impossible de modifier.",
        )

    agent_id = meta.get("agent_id") or review.get("agent_id", "")
    if agent_id != "agent_m4_email":
        raise HTTPException(
            status_code=422,
            detail=f"Ce review n'est pas un brouillon email (agent={agent_id}).",
        )

    # Appliquer les modifications sur data
    data = dict(review.get("data") or {})
    modifie = []
    if payload.objet is not None:
        data["objet"] = payload.objet
        modifie.append("objet")
    if payload.corps is not None:
        data["corps"] = payload.corps
        modifie.append("corps")

    if not modifie:
        return {
            "success": True,
            "message": "Aucune modification demandée.",
            "review_id": review_id,
        }

    # patch_review écrit dans meta — on met à jour data directement via le store
    from app.services.hitl.hitl_helper import _load_store, _save_store
    store = _load_store()
    if review_id in store["reviews"]:
        store["reviews"][review_id]["data"] = data
        from datetime import datetime as _dt
        store["reviews"][review_id]["updated_at"] = _dt.now().isoformat()
        _save_store(store)

    return {
        "success": True,
        "message": f"Brouillon modifié ({', '.join(modifie)}).",
        "review_id": review_id,
        "champs_modifies": modifie,
        "objet": data.get("objet"),
        "corps_extrait": (data.get("corps") or "")[:200] + "..." if len(data.get("corps", "")) > 200 else data.get("corps"),
    }


# =============================================================================
# ROUTE 3c — POST /email/envoyer  (A3 — envoi réel après approbation HITL)
# =============================================================================

@router.post(
    "/email/envoyer",
    summary="[M4-A3] Envoyer l'email RH après approbation HITL",
    description=(
        "Envoie réellement l'email brouillon via SMTP, **uniquement si le review est approuvé**.\n\n"
        "Flux complet :\n"
        "1. `POST /ia/rh/email/brouillon` → génère brouillon (review=pending)\n"
        "2. RH valide via `POST /hitl/reviews/{id}/approve`\n"
        "3. `POST /ia/rh/email/envoyer` → envoie l'email et marque le review comme envoyé\n\n"
        "Variables `.env` requises : `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`\n\n"
        "⚠️ Anti-doublon : un review déjà envoyé ne peut pas être renvoyé."
    ),
)
async def envoyer_email_rh(
    payload: EmailEnvoiRequest,
    orchestrator: RhOrchestrator = Depends(get_rh_orchestrator),
) -> Dict[str, Any]:
    from app.services.rh.email_rh_service import EmailRhService
    start = time.perf_counter()
    try:
        svc = EmailRhService()
        result = svc.envoyer(
            review_id=payload.review_id,
            email_destinataire=payload.email_destinataire,
        )
        elapsed = round(time.perf_counter() - start, 2)
        result["duration_seconds"] = elapsed
        return result
    except PermissionError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        _handle_exception(e, "envoyer_email_rh")
        raise HTTPException(status_code=500, detail="Erreur lors de l'envoi de l'email.")


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
        "⚠️ Résultat soumis à validation HITL avant transmission au formateur "
        "ou mise à jour du profil Backend."
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
        return _build_hitl_response(
            result,
            f"Évaluation formateur terminée — Score : {score} — {recommandation}.",
            elapsed,
        )
    except Exception as e:
        _handle_exception(e, "evaluer_formateur")
        return RouteResponse(success=False, message="")


# =============================================================================
# ROUTES SYNC BACKEND (après approbation HITL)
# =============================================================================

class SyncCandidatRequest(BaseModel):
    review_id: str
    force: bool = False


class SyncEntretienCrRequest(BaseModel):
    review_id: str
    candidat_id: str
    force: bool = False


class SyncEvaluationRequest(BaseModel):
    review_id: str
    formateur_id: str
    force: bool = False


@router.post(
    "/synchroniser/candidat",
    response_model=RouteResponse,
    summary="[M4] Sync A1 → Backend POST /rh/candidats (après approbation HITL)",
)
async def synchroniser_candidat(
    payload: SyncCandidatRequest,
    orchestrator: RhOrchestrator = Depends(get_rh_orchestrator),
) -> RouteResponse:
    start = time.perf_counter()
    try:
        result = await orchestrator.synchroniser_candidat(
            review_id=payload.review_id,
            force=payload.force,
        )
        elapsed = round(time.perf_counter() - start, 2)
        sent = (result.get("backend_sync") or {}).get("sent", False)
        return RouteResponse(
            success=True,
            message="Candidat enregistré côté Backend." if sent else "Déjà synchronisé.",
            duration_seconds=elapsed,
            review_id=payload.review_id,
            data=result,
        )
    except Exception as e:
        _handle_exception(e, "synchroniser_candidat")
        return RouteResponse(success=False, message="")


@router.post(
    "/synchroniser/entretien-cr",
    response_model=RouteResponse,
    summary="[M4] Sync A2 → Backend POST /rh/candidats/{id}/entretiens",
)
async def synchroniser_entretien_cr(
    payload: SyncEntretienCrRequest,
    orchestrator: RhOrchestrator = Depends(get_rh_orchestrator),
) -> RouteResponse:
    start = time.perf_counter()
    try:
        result = await orchestrator.synchroniser_entretien_cr(
            review_id=payload.review_id,
            candidat_id=payload.candidat_id,
            force=payload.force,
        )
        elapsed = round(time.perf_counter() - start, 2)
        sent = (result.get("backend_sync") or {}).get("sent", False)
        return RouteResponse(
            success=True,
            message="CR entretien enregistré côté Backend." if sent else "Déjà synchronisé.",
            duration_seconds=elapsed,
            review_id=payload.review_id,
            data=result,
        )
    except Exception as e:
        _handle_exception(e, "synchroniser_entretien_cr")
        return RouteResponse(success=False, message="")


@router.post(
    "/synchroniser/evaluation",
    response_model=RouteResponse,
    summary="[M4] Sync A5 → Backend PATCH /rh/formateurs/{id}",
)
async def synchroniser_evaluation(
    payload: SyncEvaluationRequest,
    orchestrator: RhOrchestrator = Depends(get_rh_orchestrator),
) -> RouteResponse:
    start = time.perf_counter()
    try:
        result = await orchestrator.synchroniser_evaluation_formateur(
            review_id=payload.review_id,
            formateur_id=payload.formateur_id,
            force=payload.force,
        )
        elapsed = round(time.perf_counter() - start, 2)
        sent = (result.get("backend_sync") or {}).get("sent", False)
        return RouteResponse(
            success=True,
            message="Évaluation formateur mise à jour côté Backend." if sent else "Déjà synchronisé.",
            duration_seconds=elapsed,
            review_id=payload.review_id,
            data=result,
        )
    except Exception as e:
        _handle_exception(e, "synchroniser_evaluation")
        return RouteResponse(success=False, message="")
