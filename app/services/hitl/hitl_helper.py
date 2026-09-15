import os
import json
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional, List

logger = logging.getLogger(__name__)

VERBOSE = os.getenv("VERBOSE_LOGS", "true").lower() == "true"


def vlog(msg: str, level: str = "info") -> None:
    """Log verbeux — contrôlé par VERBOSE_LOGS."""
    if VERBOSE:
        getattr(logger, level)(msg)

STORAGE_PATH = Path(__file__).resolve().parents[3] / "data" / "hitl_reviews.json"
STORAGE_PATH.parent.mkdir(parents=True, exist_ok=True)


def _load_store() -> Dict[str, Any]:
    """Charge le store depuis le fichier JSON."""
    if not STORAGE_PATH.exists():
        vlog(f"ℹ️  [HITL] Store inexistant → création : {STORAGE_PATH.name}")
        return {"reviews": {}, "counter": 0}

    try:
        with open(STORAGE_PATH, "r", encoding="utf-8") as f:
            store = json.load(f)
            vlog(
                f"📂 [HITL] Store chargé : "
                f"{len(store.get('reviews', {}))} reviews, "
                f"counter={store.get('counter', 0)}"
            )
            return store
    except (json.JSONDecodeError, IOError) as e:
        logger.error(f"❌ [HITL] Erreur lecture store : {e}")
        return {"reviews": {}, "counter": 0}


def _save_store(store: Dict[str, Any]) -> None:
    """Sauvegarde le store dans le fichier JSON."""
    try:
        with open(STORAGE_PATH, "w", encoding="utf-8") as f:
            json.dump(store, f, indent=2, ensure_ascii=False)
        vlog(
            f"💾 [HITL] Store sauvegardé : "
            f"{len(store.get('reviews', {}))} reviews"
        )
    except IOError as e:
        logger.error(f"❌ [HITL] Erreur écriture store : {e}")

AGENT_CRITICITY: Dict[str, str] = {
    # ── M5 — Formations ──
    "agent_1_forms":         "critical",
    "agent_2_levels":        "medium",
    "agent_3_satisfaction":  "medium",
    "agent_4_presences":     "critical",
    "agent_5_attestations":  "critical",
    "agent_6_report":        "critical",
    # ── M3 — Offres (à venir) ──
    "agent_m3_technique":    "critical",
    "agent_m3_financiere":   "critical",
    # ── M4 — RH (à venir) ──
    "agent_m4_preselection": "medium",
    "agent_m4_compte_rendu": "medium",
    "agent_m4_email":        "critical",
    # ── M7 — Facturation (à venir) ──
    "agent_m7_relance":      "critical",
    "agent_m7_facture":      "critical",
}


def create_review(
    agent_id: str,
    data: Dict[str, Any],
    summary: str,
    criticity: Optional[str] = None,
) -> str:
    """
    Crée un review pour une génération IA.

    Appelé à la FIN de chaque méthode de génération (generate/analyze).

    Args:
        agent_id: Nom de l'agent 
        data: Le dict généré par l'agent.
        summary: Résumé court pour l'affichage Frontend.
        criticity: "critical" | "medium" | "low" 

    Returns:
        Le review_id (string).
    """
    vlog("=" * 70)
    vlog(f"⏳ [HITL] create_review() — agent={agent_id}")
    vlog(f"   📝 Summary : {summary[:100]}")

    store = _load_store()

    # Générer un ID unique court : HITL-A1F-0001
    store["counter"] = store.get("counter", 0) + 1
    agent_short = agent_id.replace("agent_", "A").replace("_", "")[:3].upper()
    review_id = f"HITL-{agent_short}-{store['counter']:04d}"

    
    final_criticity = criticity or AGENT_CRITICITY.get(agent_id, "medium")

    # Créer l'entrée
    store["reviews"][review_id] = {
        "review_id": review_id,
        "agent_id": agent_id,
        "criticity": final_criticity,
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

    vlog(
        f"✅ [HITL] Review créé : {review_id} "
        f"(agent={agent_id}, criticité={final_criticity})"
    )
    vlog("=" * 70)

    return review_id


def list_pending(
    agent_id: Optional[str] = None,
    criticity: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    Liste les reviews en attente (status='pending_review').

    Args:
        agent_id: Filtre optionnel par agent.
        criticity: Filtre optionnel par criticité.

    Returns:
        Liste des reviews (version allégée, sans les données complètes).
    """
    vlog(
        f"📋 [HITL] list_pending() — "
        f"agent={agent_id or 'tous'}, criticité={criticity or 'toutes'}"
    )

    store = _load_store()
    results = []

    for review in store["reviews"].values():
        if review["status"] != "pending_review":
            continue
        if agent_id and review["agent_id"] != agent_id:
            continue
        if criticity and review["criticity"] != criticity:
            continue

        # Version allégée 
        results.append({
            "review_id": review["review_id"],
            "agent_id": review["agent_id"],
            "criticity": review["criticity"],
            "status": review["status"],
            "summary": review["summary"],
            "created_at": review["created_at"],
        })

    # Trier : critical d'abord, puis par date
    crit_priority = {"critical": 0, "medium": 1, "low": 2}
    results.sort(key=lambda r: (crit_priority.get(r["criticity"], 3), r["created_at"]))

    vlog(f"✅ [HITL] {len(results)} review(s) en attente retourné(s)")
    return results


def get_review(review_id: str) -> Optional[Dict[str, Any]]:
    """
    Récupère un review complet (avec data).

    Args:
        review_id: ID du review (ex: "HITL-A1F-0001").

    Returns:
        Le review complet ou None si non trouvé.
    """
    vlog(f"🔍 [HITL] get_review() — review_id={review_id}")

    store = _load_store()
    review = store["reviews"].get(review_id)

    if review:
        vlog(
            f"✅ [HITL] Review trouvé : {review_id} "
            f"(status={review['status']})"
        )
    else:
        logger.warning(f"⚠️  [HITL] Review non trouvé : {review_id}")

    return review


def approve_review(
    review_id: str,
    reviewer_note: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """
    Approuve un review.

    Args:
        review_id: ID du review.
        reviewer_note: Note optionnelle du réviseur.

    Returns:
        Le review mis à jour ou None si non trouvé.
    """
    vlog("=" * 70)
    vlog(f"✅ [HITL] approve_review() — review_id={review_id}")
    vlog(f"   📝 Note : {reviewer_note or '(aucune)'}")

    store = _load_store()
    if review_id not in store["reviews"]:
        logger.warning(f"⚠️  [HITL] Review non trouvé : {review_id}")
        return None

    review = store["reviews"][review_id]
    review["status"] = "approved"
    review["reviewed_at"] = datetime.now().isoformat()
    review["updated_at"] = datetime.now().isoformat()
    review["reviewer_note"] = reviewer_note

    _save_store(store)

    vlog(f"✅ [HITL] Review approuvé : {review_id}")
    vlog("=" * 70)
    return review


def reject_review(
    review_id: str,
    reason: str,
) -> Optional[Dict[str, Any]]:
    """
    Rejette un review (nécessite une régénération).

    Args:
        review_id: ID du review.
        reason: Raison du rejet.

    Returns:
        Le review mis à jour ou None si non trouvé.
    """
    vlog("=" * 70)
    vlog(f"❌ [HITL] reject_review() — review_id={review_id}")
    vlog(f"   📝 Raison : {reason[:100]}")

    store = _load_store()
    if review_id not in store["reviews"]:
        logger.warning(f"⚠️  [HITL] Review non trouvé : {review_id}")
        return None

    review = store["reviews"][review_id]
    review["status"] = "rejected"
    review["reviewed_at"] = datetime.now().isoformat()
    review["updated_at"] = datetime.now().isoformat()
    review["rejection_reason"] = reason

    _save_store(store)

    vlog(f"✅ [HITL] Review rejeté : {review_id}")
    vlog("=" * 70)
    return review

def get_stats() -> Dict[str, Any]:
    """
    Statistiques globales des reviews.

    Returns:
        {
            "total": int,
            "pending": int,
            "approved": int,
            "rejected": int,
            "by_agent": {...},
            "by_criticity": {"critical": int, "medium": int, "low": int},
        }
    """
    vlog("📊 [HITL] get_stats()")

    store = _load_store()
    stats = {
        "total": len(store["reviews"]),
        "pending": 0,
        "approved": 0,
        "rejected": 0,
        "by_agent": {},
        "by_criticity": {"critical": 0, "medium": 0, "low": 0},
    }

    # ── Mapping status → clé stats ──
    STATUS_MAP = {
        "pending_review": "pending",
        "approved": "approved",
        "rejected": "rejected",
    }

    for review in store["reviews"].values():
        raw_status = review["status"]
        # ⚠️ Normaliser : 'pending_review' → 'pending'
        status = STATUS_MAP.get(raw_status, raw_status)

        # Incrémenter le compteur global
        if status in ("pending", "approved", "rejected"):
            stats[status] += 1

        # Par agent
        agent = review["agent_id"]
        if agent not in stats["by_agent"]:
            stats["by_agent"][agent] = {"pending": 0, "approved": 0, "rejected": 0}
        if status in ("pending", "approved", "rejected"):
            stats["by_agent"][agent][status] += 1

        # Par criticité
        crit = review["criticity"]
        stats["by_criticity"][crit] = stats["by_criticity"].get(crit, 0) + 1

    vlog(
        f"✅ [HITL] Stats : "
        f"total={stats['total']}, "
        f"pending={stats['pending']}, "
        f"approved={stats['approved']}, "
        f"rejected={stats['rejected']}"
    )
    return stats

vlog(
    f"📦 Module 'hitl_helper' (générique v2.0.0) chargé — "
    f"Store : {STORAGE_PATH}"
)