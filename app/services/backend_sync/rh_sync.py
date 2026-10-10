# app/services/backend_sync/rh_sync.py
# ============================================================
# SYNC M4 — RH IA ↔ Backend
# ============================================================
# Routes Backend utilisées :
#   POST  /rh/formateurs                    — créer un formateur
#   PATCH /rh/formateurs/{id}               — mettre à jour (score, recommandation)
#   POST  /rh/candidats                     — créer un dossier candidat
#   PATCH /rh/candidats/{id}                — mettre à jour (décision, review_id)
#   POST  /rh/candidats/{id}/entretiens     — créer un entretien
#   PATCH /rh/entretiens/{id}               — mettre à jour (CR, email, décision)
#
# ⚠️ HITL : n'appeler sync_*() qu'APRÈS approbation humaine.
# ============================================================

import logging
from typing import Any, Dict, Optional

from app.services.backend_sync import base_sync

logger = logging.getLogger(__name__)


async def sync_evaluation_formateur(
    formateur_id: str,
    score_moyen: Optional[float],
    nb_sessions: Optional[str],
    recommandation: Optional[str],
    notes_internes: Optional[str] = None,
) -> dict[str, Any]:
    """
    Met à jour le profil d'un formateur avec les résultats de l'évaluation A5
    (PATCH /rh/formateurs/{id}).

    Appelé par A5 (EvaluationFormateurService) — document interne, pas de HITL.
    """
    result = base_sync.new_result()
    if not result["enabled"]:
        logger.info("ℹ️ Backend sync DÉSACTIVÉ — évaluation formateur non envoyée")
        return result

    if not base_sync.is_valid_uuid(formateur_id):
        result["error"] = "formateur_id n'est pas un UUID valide"
        return result

    payload: dict[str, Any] = {}
    if score_moyen is not None:
        payload["score_moyen"] = score_moyen
    if nb_sessions is not None:
        payload["nb_sessions"] = str(nb_sessions)
    if recommandation is not None:
        payload["recommandation"] = recommandation
    if notes_internes is not None:
        payload["notes_internes"] = notes_internes[:2000]

    if not payload:
        result["error"] = "Aucune donnée à mettre à jour"
        return result

    response = await base_sync.backend_request(
        "PATCH", f"/rh/formateurs/{formateur_id}", json=payload
    )
    result["sent"] = response["ok"]
    result["error"] = response.get("error")
    if response["ok"]:
        result["verified"] = True
    return result


async def sync_candidat_to_backend(
    nom: str,
    poste_vise: str,
    score_preselection: Optional[float] = None,
    decision_preselection: Optional[str] = None,
    review_id_preselection: Optional[str] = None,
) -> dict[str, Any]:
    """
    Crée un dossier candidat côté Backend (POST /rh/candidats).
    Appelé après approbation HITL de la présélection (A1).
    """
    result = base_sync.new_result(candidat_id=None)
    if not result["enabled"]:
        return result

    payload: dict[str, Any] = {
        "nom": nom[:200],
        "poste_vise": poste_vise[:200],
    }
    if score_preselection is not None:
        payload["score_preselection"] = score_preselection
    if decision_preselection is not None:
        payload["decision_preselection"] = decision_preselection
    if review_id_preselection is not None:
        payload["review_id_preselection"] = str(review_id_preselection)[:100]

    response = await base_sync.backend_request("POST", "/rh/candidats", json=payload)
    result["sent"] = response["ok"]
    result["error"] = response.get("error")
    if response["ok"] and isinstance(response["data"], dict):
        result["candidat_id"] = response["data"].get("id")
        result["verified"] = True
    return result


async def sync_entretien_cr_to_backend(
    candidat_id: str,
    compte_rendu: str,
    decision: Optional[str] = None,
    interviewers: Optional[str] = None,
    date_entretien: Optional[str] = None,
    review_id_entretien: Optional[str] = None,
) -> dict[str, Any]:
    """
    Crée un entretien avec son CR approuvé (POST /rh/candidats/{id}/entretiens).
    Appelé après approbation HITL du CR (A2).
    """
    result = base_sync.new_result(entretien_id=None)
    if not result["enabled"]:
        return result

    if not base_sync.is_valid_uuid(candidat_id):
        result["error"] = "candidat_id n'est pas un UUID valide"
        return result

    payload: dict[str, Any] = {
        "compte_rendu": compte_rendu[:10000] if compte_rendu else "",
    }
    if decision:
        payload["decision"] = decision
    if interviewers:
        payload["interviewers"] = interviewers[:500]
    if date_entretien:
        payload["date_entretien"] = date_entretien[:20]
    if review_id_entretien:
        payload["review_id_entretien"] = str(review_id_entretien)[:100]

    response = await base_sync.backend_request(
        "POST", f"/rh/candidats/{candidat_id}/entretiens", json=payload
    )
    result["sent"] = response["ok"]
    result["error"] = response.get("error")
    if response["ok"] and isinstance(response["data"], dict):
        result["entretien_id"] = response["data"].get("id")
        result["verified"] = True
    return result
