# app/services/backend_sync/preparation_sync.py
# ============================================================
# SYNC PRÉPARATION — Emploi du temps IA → Backend
# ============================================================
# Les routes du CDC pour la Préparation (/projets, /formateurs,
# /salles, /projets/{id}/edt, /projets/{id}/budget) N'EXISTENT PAS
# encore côté Backend (aucune table correspondante).
#
# En attendant, l'EDT est enregistré avec les routes réelles :
#   POST /sessions                    SessionCreate {titre, client,
#                                     date_debut, date_fin, formateur_id}
#   POST /sessions/{id}/seances       SeanceCreate {date, duree, theme}
# → 1 Session = la formation, 1 Séance = 1 jour de l'EDT.
#
# Le BUDGET n'est PAS persisté : aucune route Backend ne le reçoit.
# → Dépendance Backend : POST /api/v1/projets/{id}/budget (CDC Étape 3).
#
# Notes de contrat Backend :
#   - Session.date_fin est NOT NULL en base (optionnelle dans le schéma)
#     → toujours envoyée ici ;
#   - titre / client limités à 50 caractères, theme à 100, duree à 25 ;
#   - formateur_id référence users.id (UUID) : ignoré s'il n'est pas un UUID.
#
# ⚠️ HITL : à n'appeler qu'APRÈS approbation humaine de la préparation
#    (chaque appel crée une NOUVELLE session côté Backend).
# ============================================================

import logging
import re
from typing import Any, Dict, List, Optional

from app.services.backend_sync import base_sync

logger = logging.getLogger(__name__)

_TITRE_MAX = 50
_CLIENT_MAX = 50
_THEME_MAX = 100
_DUREE_MAX = 25
_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}")

_BUDGET_REASON = (
    "Aucune route Backend pour le budget "
    "(POST /projets/{id}/budget du CDC absent) — budget non persisté"
)


def _iso_date(value: Any) -> Optional[str]:
    text = str(value or "").strip()
    return text[:10] if _DATE_RE.match(text) else None


def _minutes(session: Any) -> int:
    try:
        return int(session.get("duree_minutes") or 0)
    except (AttributeError, TypeError, ValueError):
        return 0


def _seance_payload(jour: Dict[str, Any], date_iso: str) -> Dict[str, Any]:
    """Un jour d'EDT → SeanceCreate (duree et theme jamais vides : NOT NULL en base)."""
    sessions = [s for s in (jour.get("sessions") or []) if isinstance(s, dict)]

    total_minutes = sum(_minutes(s) for s in sessions)
    duree = f"{total_minutes / 60:g}h" if total_minutes else "1 jour"

    modules: List[str] = []
    for s in sessions:
        module = str(s.get("module") or "").strip()
        if module and module not in modules:
            modules.append(module)

    return {
        "date": date_iso,
        "duree": base_sync.truncate(duree, _DUREE_MAX),
        "theme": base_sync.truncate(", ".join(modules), _THEME_MAX) or "Formation",
    }


async def sync_preparation_to_backend(
    edt: Dict[str, Any],
    projet_info: Optional[Dict[str, Any]] = None,
    budget: Optional[Dict[str, Any]] = None,
    formateur_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Enregistre la préparation côté Backend (session + séances).

    Args:
        edt: résultat de EDTGeneratorService.generate()
            ({titre_formation, jours: [{date, sessions: [...]}]}).
        projet_info: {"client": ...} (facultatif).
        budget: résultat du BudgetCalculatorService (signalé comme non
            persisté, voir en-tête).
        formateur_id: UUID d'un utilisateur Backend (facultatif).

    Returns:
        Résultat standard (base_sync.new_result) pour la SESSION, plus :
          "seances": {"sent": int, "failed": int}
          "budget":  None ou {"sent": False, "skipped": True, "reason": str}
    """
    result = base_sync.new_result(seances={"sent": 0, "failed": 0}, budget=None)
    if not result["enabled"]:
        logger.info("ℹ️ Backend sync DÉSACTIVÉ — préparation non envoyée")
        return result

    jours = [j for j in (edt or {}).get("jours", []) if isinstance(j, dict)]
    dated = [(j, _iso_date(j.get("date"))) for j in jours]
    dated = [(j, d) for j, d in dated if d]
    if not dated:
        result["error"] = "EDT sans jour daté (YYYY-MM-DD) — rien à envoyer"
        return result

    dates = sorted(d for _, d in dated)
    client = base_sync.truncate((projet_info or {}).get("client"), _CLIENT_MAX)
    session_payload: Dict[str, Any] = {
        "titre": base_sync.truncate(edt.get("titre_formation"), _TITRE_MAX)
        or "Formation",
        "date_debut": dates[0],
        "date_fin": dates[-1],
    }
    if client:
        session_payload["client"] = client
    if base_sync.is_valid_uuid(formateur_id):
        session_payload["formateur_id"] = str(formateur_id)

    session = await base_sync.post_and_verify(
        "/sessions", session_payload, label="session (EDT)"
    )
    for key in ("sent", "skipped", "verified", "resource_id",
                "status_code", "data", "error"):
        result[key] = session[key]

    if budget:
        result["budget"] = {"sent": False, "skipped": True,
                            "reason": _BUDGET_REASON}

    if not session["sent"] or not session["resource_id"]:
        return result

    # Une séance par jour de l'EDT (pas de GET de contrôle : le Backend
    # n'expose pas GET /sessions/seances/{id})
    for jour, date_iso in dated:
        seance = await base_sync.post_and_verify(
            f"/sessions/{session['resource_id']}/seances",
            _seance_payload(jour, date_iso),
            verify=False,
            label="séance",
        )
        result["seances"]["sent" if seance["sent"] else "failed"] += 1

    return result
