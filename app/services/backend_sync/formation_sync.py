# app/services/backend_sync/formation_sync.py
# ============================================================
# SYNC M5 — Formations IA ↔ Backend
# ============================================================
# Routes Backend utilisées (contrat réel, app/api/v1/endpoints/) :
#   GET  /sessions/{id}                       lecture d'une session
#   POST /sessions/seances/{id}/presences     PresenceCreate
#        {participant_id (UUID), statut, source}        DIRECTION/FORMATEUR
#   POST /documents/attestations/{session_id} sans corps ; le Backend
#        crée lui-même les attestations des participants PRÉSENT
#        au moins une fois                              DIRECTION/FORMATEUR
#   GET  /documents/{id}                      contrôle
#
# Enums Backend : statut = PRESENT | ABSENT | EXCUSE
#                 source = MANUEL | GOOGLE_FORMS
#
# Cette sync est volontairement légère : sessions, séances et
# participants sont créés par le Backend (CRUD), pas par l'IA.
#
# ⚠️ HITL : les attestations (criticité « critical ») ne doivent être
#    demandées au Backend qu'APRÈS approbation humaine.
# ⚠️ Les agents M5 (stabilisés) ne sont PAS modifiés : ces fonctions
#    sont à appeler depuis les routes/orchestrateur quand décidé.
# ============================================================

import logging
from typing import Any, Dict, List, Optional

from app.services.backend_sync import base_sync

logger = logging.getLogger(__name__)

_STATUTS = {
    "present": "PRESENT", "présent": "PRESENT", "p": "PRESENT",
    "absent": "ABSENT", "a": "ABSENT",
    "excuse": "EXCUSE", "excusé": "EXCUSE", "excusee": "EXCUSE",
    "excusée": "EXCUSE",
}
_SOURCES = ("MANUEL", "GOOGLE_FORMS")


def map_statut_presence(value: Any) -> Optional[str]:
    """'présent' / 'Absent' / 'EXCUSE'… → enum Backend, ou None si inconnu."""
    return _STATUTS.get(str(value or "").strip().lower())


async def fetch_session(session_id: str) -> Optional[Dict[str, Any]]:
    """
    Lit une session Backend (GET /sessions/{id}) : titre, client, dates.
    Permet de construire `session_info` à partir d'un session_id
    (contrat du CDC pour les routes M5).

    Returns:
        Le dict Backend, ou None (id invalide, introuvable, erreur).
    """
    if not base_sync.is_valid_uuid(session_id):
        logger.warning("⚠️ fetch_session : session_id n'est pas un UUID")
        return None

    response = await base_sync.backend_request("GET", f"/sessions/{session_id}")
    if response["ok"] and isinstance(response["data"], dict):
        return response["data"]

    logger.warning("⚠️ Session non récupérée : %s", response["error"])
    return None


async def sync_presences_to_backend(
    seance_id: str,
    presences: List[Dict[str, Any]],
    source: str = "GOOGLE_FORMS",
) -> Dict[str, Any]:
    """
    Enregistre des présences (ex. réponses Google Forms) sur une séance.

    Args:
        seance_id: UUID de la séance Backend.
        presences: [{"participant_id": UUID, "statut": "present|absent|excuse",
            "source": optionnel}] — les entrées invalides sont comptées
            en échec, sans bloquer les autres.
        source: source par défaut (MANUEL | GOOGLE_FORMS).

    Returns:
        Résultat standard + "sent_count" / "failed_count".
        `sent` est True dès qu'une présence est créée.
    """
    result = base_sync.new_result(sent_count=0, failed_count=0)
    if not result["enabled"]:
        logger.info("ℹ️ Backend sync DÉSACTIVÉ — présences non envoyées")
        return result

    if not base_sync.is_valid_uuid(seance_id):
        result["error"] = "seance_id invalide (UUID attendu)"
        return result
    if source not in _SOURCES:
        result["error"] = f"source invalide '{source}' ({' | '.join(_SOURCES)})"
        return result

    for entry in presences or []:
        statut = map_statut_presence((entry or {}).get("statut"))
        entry_source = (entry or {}).get("source", source)
        if (
            not base_sync.is_valid_uuid((entry or {}).get("participant_id"))
            or not statut
            or entry_source not in _SOURCES
        ):
            result["failed_count"] += 1
            continue

        created = await base_sync.post_and_verify(
            f"/sessions/seances/{seance_id}/presences",
            {
                "participant_id": str(entry["participant_id"]),
                "statut": statut,
                "source": entry_source,
            },
            verify=False,
            label="présence",
        )
        if created["skipped"]:
            # Même route pour toutes les entrées : inutile d'insister
            result["skipped"] = True
            result["status_code"] = created["status_code"]
            result["error"] = created["error"]
            return result

        result["status_code"] = created["status_code"]
        if created["sent"]:
            result["sent_count"] += 1
        else:
            result["failed_count"] += 1
            result["error"] = created["error"]

    result["sent"] = result["sent_count"] > 0
    return result


async def sync_attestations_to_backend(session_id: str) -> Dict[str, Any]:
    """
    Demande au Backend de créer les attestations de la session
    (POST /documents/attestations/{session_id}).

    Returns:
        Résultat standard + "count" (attestations de la session) et
        "ids" (UUID). `verified` : GET de contrôle sur la première.
    """
    result = base_sync.new_result(count=0, ids=[])
    if not result["enabled"]:
        logger.info("ℹ️ Backend sync DÉSACTIVÉ — attestations non demandées")
        return result

    if not base_sync.is_valid_uuid(session_id):
        result["error"] = "session_id invalide (UUID attendu)"
        return result

    response = await base_sync.backend_request(
        "POST", f"/documents/attestations/{session_id}"
    )
    result["status_code"] = response["status_code"]

    if response["absent"]:
        result["skipped"] = True
        result["error"] = f"Endpoint ou session absent ({response['error']})"
        logger.warning("⚠️ Sync attestations ignorée : %s", result["error"])
        return result
    if not response["ok"]:
        result["error"] = response["error"]
        logger.warning("❌ Sync attestations échouée : %s", result["error"])
        return result

    documents = response["data"] if isinstance(response["data"], list) else []
    result["ids"] = [
        str(d["id"]) for d in documents
        if isinstance(d, dict) and d.get("id") is not None
    ]
    result["count"] = len(result["ids"])
    result["sent"] = True

    if result["ids"]:
        check = await base_sync.backend_request(
            "GET", f"/documents/{result['ids'][0]}"
        )
        result["verified"] = check["ok"]

    logger.info(
        "✅ Sync attestations : %d attestation(s), vérifié=%s",
        result["count"], result["verified"]
    )
    return result
