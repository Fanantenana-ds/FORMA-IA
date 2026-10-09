# app/services/backend_sync/preparation_sync.py
# ============================================================
# SYNC PRÉPARATION — Emploi du temps IA → Backend
# ============================================================
# Routes Backend utilisées (contrat réel, app/api/v1/endpoints/projet.py) :
#   POST /projets                ProjetCreate {titre, client, date_debut,
#                                date_fin, statut, notes, opportunite_id}
#   POST /projets/{id}/edt       EdtSessionCreate {date, heure_debut,
#                                heure_fin, module, formateur_id}
#   GET  /projets/{id}           contrôle après création du projet
#
# Le BUDGET est envoyé via POST /projets/{id}/budget après création
# du projet quand le dict budget est fourni (BudgetCreate :
# cout_formateur, cout_salle, cout_supports, valide).
#
# Notes de contrat Backend :
#   - titre limité à 100 car., client à 100 car. ;
#   - module limité à 200 car. (EdtSessionCreate) ;
#   - formateur_id référence users.id (UUID) : ignoré sinon.
#
# ⚠️ HITL : à n'appeler qu'APRÈS approbation humaine de la préparation
#    (chaque appel crée un NOUVEAU projet côté Backend).
# ============================================================

import logging
import re
from typing import Any, Dict, List, Optional, Tuple

from app.services.backend_sync import base_sync

logger = logging.getLogger(__name__)

_TITRE_MAX = 100
_CLIENT_MAX = 100
_MODULE_MAX = 200
_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}")
_TIME_RE = re.compile(r"^\d{2}:\d{2}")

_BUDGET_FIELDS = ("cout_formateur", "cout_salle", "cout_supports")


def _budget_payload(budget: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Convertit le résultat de BudgetCalculatorService → BudgetCreate."""
    try:
        cout_formateur = float(budget.get("cout_formateur") or 0)
        cout_salle = float(budget.get("cout_salle") or 0)
        cout_supports = float(budget.get("cout_supports") or 0)
    except (TypeError, ValueError):
        return None
    if cout_formateur == 0 and cout_salle == 0 and cout_supports == 0:
        return None
    return {
        "cout_formateur": cout_formateur,
        "cout_salle": cout_salle,
        "cout_supports": cout_supports,
        "valide": False,
    }


def _iso_date(value: Any) -> str | None:
    text = str(value or "").strip()
    return text[:10] if _DATE_RE.match(text) else None


def _iso_time(value: Any) -> Optional[str]:
    text = str(value or "").strip()
    return text[:5] if _TIME_RE.match(text) else None


def _seance_payload(jour: dict[str, Any], date_iso: str) -> dict[str, Any]:
    """Un jour d'EDT → SeanceCreate (duree et theme jamais vides : NOT NULL en base)."""
    sessions = [s for s in (jour.get("sessions") or []) if isinstance(s, dict)]

    total_minutes = sum(_minutes(s) for s in sessions)
    duree = f"{total_minutes / 60:g}h" if total_minutes else "1 jour"

    modules: list[str] = []
    for s in sessions:
        module = str(s.get("module") or "").strip()
        if module and module not in modules:
            modules.append(module)

    payload: Dict[str, Any] = {"date": date_iso}

    heure_debut = _iso_time(jour.get("heure_debut"))
    heure_fin = _iso_time(jour.get("heure_fin"))
    if heure_debut:
        payload["heure_debut"] = heure_debut
    if heure_fin:
        payload["heure_fin"] = heure_fin

    module_str = base_sync.truncate(", ".join(modules), _MODULE_MAX)
    if module_str:
        payload["module"] = module_str

    if base_sync.is_valid_uuid(formateur_id):
        payload["formateur_id"] = str(formateur_id)

    return payload


async def sync_preparation_to_backend(
    edt: dict[str, Any],
    projet_info: dict[str, Any] | None = None,
    budget: dict[str, Any] | None = None,
    formateur_id: str | None = None,
) -> dict[str, Any]:
    """
    Enregistre la préparation côté Backend (projet + EDT).

    Args:
        edt: résultat de EDTGeneratorService.generate()
            ({titre_formation, jours: [{date, sessions: [...]}]}).
        projet_info: {"client": ...} (facultatif).
        budget: résultat du BudgetCalculatorService (non persisté,
            voir en-tête du fichier).
        formateur_id: UUID d'un utilisateur Backend (facultatif).
        opportunite_id: UUID de l'opportunité liée (facultatif).
        offre_id: UUID de l'offre liée (facultatif).

    Returns:
        Résultat standard (base_sync.new_result) pour le PROJET, plus :
          "edt":    {"sent": int, "failed": int}
          "budget": None ou {"sent": False, "skipped": True, "reason": str}
    """
    result = base_sync.new_result(edt={"sent": 0, "failed": 0}, budget=None)
    if not result["enabled"]:
        logger.info("ℹ️ Backend sync DÉSACTIVÉ — préparation non envoyée")
        return result

    jours = [j for j in (edt or {}).get("jours", []) if isinstance(j, dict)]
    dated: List[Tuple[Dict[str, Any], str]] = [
        (j, d)
        for j in jours
        if (d := _iso_date(j.get("date"))) is not None
    ]
    if not dated:
        result["error"] = "EDT sans jour daté (YYYY-MM-DD) — rien à envoyer"
        return result

    dates = sorted(d for _, d in dated)
    client = base_sync.truncate((projet_info or {}).get("client"), _CLIENT_MAX)
    session_payload: dict[str, Any] = {
        "titre": base_sync.truncate(edt.get("titre_formation"), _TITRE_MAX)
        or "Formation",
        "date_debut": dates[0],
        "date_fin": dates[-1],
        "statut": "brouillon",
    }
    if client:
        projet_payload["client"] = client
    if base_sync.is_valid_uuid(opportunite_id):
        projet_payload["opportunite_id"] = str(opportunite_id)
    if base_sync.is_valid_uuid(offre_id):
        projet_payload["offre_id"] = str(offre_id)

    projet = await base_sync.post_and_verify(
        "/projets", projet_payload, label="projet (préparation)"
    )
    for key in ("sent", "skipped", "verified", "resource_id",
                "status_code", "data", "error"):
        result[key] = projet[key]

    if not projet["sent"] or not projet["resource_id"]:
        return result

    for jour, date_iso in dated:
        edt_entry = await base_sync.post_and_verify(
            f"/projets/{projet['resource_id']}/edt",
            _edt_payload(jour, date_iso, formateur_id),
            verify=False,
            label="edt",
        )
        result["edt"]["sent" if edt_entry["sent"] else "failed"] += 1

    if budget and isinstance(budget, dict):
        budget_payload = _budget_payload(budget)
        if budget_payload:
            budget_result = await base_sync.post_and_verify(
                f"/projets/{projet['resource_id']}/budget",
                budget_payload,
                verify=False,
                label="budget",
            )
            result["budget"] = {
                "sent": budget_result["sent"],
                "error": budget_result.get("error"),
            }
        else:
            result["budget"] = {
                "sent": False,
                "skipped": True,
                "reason": "Budget sans cout_formateur/cout_salle/cout_supports",
            }

    return result
