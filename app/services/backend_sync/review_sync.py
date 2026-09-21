# app/services/backend_sync/review_sync.py
# ============================================================
# SYNC APRÈS APPROBATION HITL — garde-fous communs (M3, Préparation)
# ============================================================
# Règle du CDC : aucun contenu généré par l'IA n'atteint le Backend
# sans validation humaine. Ce module applique cette règle :
#
#   1. load_approved_review()  refuse tout review qui n'est pas
#      « approved » (ou qui n'appartient pas au bon agent) ;
#   2. sync_once()             n'exécute la synchronisation qu'UNE fois
#      par review (chaque envoi crée une NOUVELLE ressource côté
#      Backend : session, offre…). Un registre local mémorise le résultat.
#      force=True permet de renvoyer volontairement.
#
# Registre : data/backend_sync_registry.json (dossier « data/ » ignoré
# par git, comme data/hitl_reviews.json).
#
# ⚠️ hitl_helper.py n'est PAS modifié : le registre est séparé.
# ============================================================

import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Awaitable, Callable, Dict, Iterable, Optional, Tuple

from app.services.hitl import get_review

logger = logging.getLogger(__name__)

REGISTRY_PATH = (
    Path(__file__).resolve().parents[3] / "data" / "backend_sync_registry.json"
)


# ============================================================
# REGISTRE (fichier JSON)
# ============================================================

def _load_registry() -> Dict[str, Any]:
    if not REGISTRY_PATH.exists():
        return {}
    try:
        with open(REGISTRY_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (json.JSONDecodeError, OSError) as exc:
        logger.error("❌ Registre de sync illisible : %s", exc)
        return {}


def _save_registry(registry: Dict[str, Any]) -> None:
    REGISTRY_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = REGISTRY_PATH.with_suffix(".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(registry, f, indent=2, ensure_ascii=False)
    os.replace(tmp, REGISTRY_PATH)  # écriture atomique


def get_synced(review_id: str) -> Optional[Dict[str, Any]]:
    """Entrée du registre pour ce review, ou None s'il n'a jamais été envoyé."""
    return _load_registry().get(review_id)


def mark_synced(review_id: str, resume: Dict[str, Any]) -> None:
    registry = _load_registry()
    registry[review_id] = {
        "synced_at": datetime.now().isoformat(),
        "backend_sync": resume,
    }
    _save_registry(registry)


# ============================================================
# GARDE-FOU HITL
# ============================================================

def load_approved_review(
    review_id: str,
    agent_ids: Iterable[str],
) -> Dict[str, Any]:
    """
    Retourne le review complet, à condition qu'il soit APPROUVÉ et produit
    par l'un des agents attendus.

    Raises:
        ValueError: review introuvable, non approuvé, ou d'un autre agent.
    """
    agents = tuple(agent_ids)
    review = get_review(review_id)

    if not review:
        raise ValueError(f"Review '{review_id}' introuvable.")

    if review.get("status") != "approved":
        raise ValueError(
            f"Review '{review_id}' non approuvé (statut : "
            f"{review.get('status')}). La synchronisation avec le Backend "
            f"exige une validation humaine préalable."
        )

    if review.get("agent_id") not in agents:
        raise ValueError(
            f"Review '{review_id}' produit par '{review.get('agent_id')}' : "
            f"attendu {' ou '.join(agents)}."
        )

    return review


# ============================================================
# EXÉCUTION UNIQUE
# ============================================================

def describe_sync(result: Dict[str, Any]) -> Tuple[bool, str]:
    """(succès, message) lisible à partir du retour de sync_once()."""
    sync = result.get("backend_sync") or {}

    if result.get("already_synced"):
        return True, "Déjà synchronisé avec le Backend : aucun nouvel envoi."
    if not sync.get("enabled"):
        return False, "Synchronisation Backend désactivée (BACKEND_SYNC_ENABLED=false)."
    if sync.get("sent"):
        controle = "vérifié" if sync.get("verified") else "non vérifié par GET"
        return True, f"Synchronisé avec le Backend ({controle})."
    if sync.get("skipped"):
        return False, f"Non envoyé, route Backend absente : {sync.get('error')}"
    return False, f"Échec de la synchronisation : {sync.get('error')}"


def resume_result(result: Dict[str, Any]) -> Dict[str, Any]:
    """Résultat de sync sans le corps de la réponse Backend (volumineux)."""
    return {k: v for k, v in result.items() if k != "data"}


async def sync_once(
    review_id: str,
    sync_call: Callable[[], Awaitable[Dict[str, Any]]],
    force: bool = False,
) -> Dict[str, Any]:
    """
    Exécute `sync_call()` une seule fois par review.

    Returns:
        {"review_id", "already_synced": bool, "synced_at": str|None,
         "backend_sync": <résultat résumé>}
    """
    previous = get_synced(review_id)
    if previous and not force:
        logger.info("ℹ️ Review %s déjà synchronisé : aucun nouvel envoi", review_id)
        return {
            "review_id": review_id,
            "already_synced": True,
            "synced_at": previous.get("synced_at"),
            "backend_sync": previous.get("backend_sync"),
        }

    resume = resume_result(await sync_call())

    synced_at = None
    if resume.get("sent"):
        mark_synced(review_id, resume)
        synced_at = get_synced(review_id)["synced_at"]

    return {
        "review_id": review_id,
        "already_synced": False,
        "synced_at": synced_at,
        "backend_sync": resume,
    }
