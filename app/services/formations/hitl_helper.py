import os
import json
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional, List

logger = logging.getLogger(__name__)

VERBOSE = os.getenv("VERBOSE_LOGS", "true").lower() == "true"


def vlog(msg: str, level: str = "info") -> None:
    if VERBOSE:
        getattr(logger, level)(msg)


# ============================================================
# STORAGE
# ============================================================
STORAGE_PATH = Path(__file__).resolve().parents[3] / "data" / "hitl_reviews.json"
STORAGE_PATH.parent.mkdir(parents=True, exist_ok=True)


def _load_store() -> Dict[str, Any]:
    if not STORAGE_PATH.exists():
        return {"reviews": {}, "counter": 0}
    try:
        with open(STORAGE_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError) as e:
        logger.error(f"❌ Erreur lecture store HITL : {e}")
        return {"reviews": {}, "counter": 0}


def _save_store(store: Dict[str, Any]) -> None:
    try:
        with open(STORAGE_PATH, "w", encoding="utf-8") as f:
            json.dump(store, f, indent=2, ensure_ascii=False)
    except IOError as e:
        logger.error(f"❌ Erreur écriture store HITL : {e}")


# ============================================================
# CRITICITÉ PAR AGENT
# ============================================================
AGENT_CRITICITY: Dict[str, str] = {
    "agent_1_forms":         "critical",
    "agent_2_levels":        "medium",
    "agent_3_satisfaction":  "medium",
    "agent_4_presences":     "critical",
    "agent_5_attestations":  "critical",
    "agent_6_report":        "critical",
}


# ============================================================
# API PUBLIQUE
# ============================================================

def create_review(
    agent_id: str,
    data: Dict[str, Any],
    summary: str,
    criticity: Optional[str] = None,
) -> str:
    """Crée un review → retourne review_id."""
    store = _load_store()

    store["counter"] = store.get("counter", 0) + 1
    agent_short = agent_id.replace("agent_", "A").replace("_", "")[:3].upper()
    review_id = f"HITL-{agent_short}-{store['counter']:04d}"

    store["reviews"][review_id] = {
        "review_id": review_id,
        "agent_id": agent_id,
        "criticity": criticity or AGENT_CRITICITY.get(agent_id, "medium"),
        "status": "pending_review",
        "summary": summary,
        "created_at": datetime.now().isoformat(),
        "updated_at": datetime.now().isoformat(),
        "reviewed_at": None,
        "reviewer_note": None,
        "rejection_reason": None,
        "data": data,
    }

    _save_store(store)
    vlog(f"⏳ [HITL] Review créé : {review_id} (agent={agent_id})")
    return review_id


def list_pending(
    agent_id: Optional[str] = None,
    criticity: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Liste les reviews en attente."""
    store = _load_store()
    results = []

    for review in store["reviews"].values():
        if review["status"] != "pending_review":
            continue
        if agent_id and review["agent_id"] != agent_id:
            continue
        if criticity and review["criticity"] != criticity:
            continue

        results.append({
            "review_id": review["review_id"],
            "agent_id": review["agent_id"],
            "criticity": review["criticity"],
            "status": review["status"],
            "summary": review["summary"],
            "created_at": review["created_at"],
        })

    crit_priority = {"critical": 0, "medium": 1, "low": 2}
    results.sort(key=lambda r: (crit_priority.get(r["criticity"], 3), r["created_at"]))
    return results


def get_review(review_id: str) -> Optional[Dict[str, Any]]:
    """Récupère un review complet."""
    store = _load_store()
    return store["reviews"].get(review_id)


def approve_review(
    review_id: str,
    reviewer_note: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """Approuve un review."""
    store = _load_store()
    if review_id not in store["reviews"]:
        return None

    review = store["reviews"][review_id]
    review["status"] = "approved"
    review["reviewed_at"] = datetime.now().isoformat()
    review["updated_at"] = datetime.now().isoformat()
    review["reviewer_note"] = reviewer_note

    _save_store(store)
    vlog(f"✅ [HITL] Review approuvé : {review_id}")
    return review


def reject_review(
    review_id: str,
    reason: str,
) -> Optional[Dict[str, Any]]:
    """Rejette un review."""
    store = _load_store()
    if review_id not in store["reviews"]:
        return None

    review = store["reviews"][review_id]
    review["status"] = "rejected"
    review["reviewed_at"] = datetime.now().isoformat()
    review["updated_at"] = datetime.now().isoformat()
    review["rejection_reason"] = reason

    _save_store(store)
    vlog(f"❌ [HITL] Review rejeté : {review_id} — {reason[:80]}")
    return review


def get_stats() -> Dict[str, Any]:
    """Statistiques globales."""
    store = _load_store()
    stats = {
        "total": len(store["reviews"]),
        "pending": 0,
        "approved": 0,
        "rejected": 0,
        "by_agent": {},
        "by_criticity": {"critical": 0, "medium": 0, "low": 0},
    }

    for review in store["reviews"].values():
        status = review["status"]
        stats[status] = stats.get(status, 0) + 1

        agent = review["agent_id"]
        if agent not in stats["by_agent"]:
            stats["by_agent"][agent] = {"pending": 0, "approved": 0, "rejected": 0}
        stats["by_agent"][agent][status] = stats["by_agent"][agent].get(status, 0) + 1

        crit = review["criticity"]
        stats["by_criticity"][crit] = stats["by_criticity"].get(crit, 0) + 1

    return stats