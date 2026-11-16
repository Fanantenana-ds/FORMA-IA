# app/services/rag/response_cache_service.py
# ============================================================
# CACHE DES RÉPONSES LLM — data/rag/response_cache/{tenant}.json
# ============================================================
# Évite de rappeler Voyage + LLM pour des questions identiques ou
# très proches dans la même session/formation.
# TTL 1 heure ; max MAX_ENTREES entrées (LRU simple par timestamp).
# ============================================================

import hashlib
import json
import logging
import os
import time
from pathlib import Path
from typing import Any

from app.services.rag.query_cache_service import normaliser_texte

logger = logging.getLogger(__name__)

DOSSIER_DEFAUT = Path(__file__).resolve().parents[3] / "data" / "rag" / "response_cache"
TTL_SECONDES = int(os.getenv("RAG_RESPONSE_CACHE_TTL", "3600"))
MAX_ENTREES = int(os.getenv("RAG_RESPONSE_CACHE_MAX", "200"))


def _chemin_cache() -> Path:
    dossier = DOSSIER_DEFAUT
    try:
        from app.core.tenant_context import get_tenant_id
        tenant_id = get_tenant_id()
        if tenant_id is not None:
            dossier = dossier / "tenants" / str(tenant_id)
    except Exception:
        pass
    dossier.mkdir(parents=True, exist_ok=True)
    return dossier / "cache.json"


def _cle(question: str, collection: str, formation_code: str | None, session_id: str | None) -> str:
    normalise = normaliser_texte(question)
    contenu = f"{normalise}|{collection}|{formation_code or ''}|{session_id or ''}"
    return hashlib.sha256(contenu.encode()).hexdigest()[:16]


def _charger(chemin: Path) -> dict:
    if not chemin.exists():
        return {}
    try:
        with open(chemin, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {}


def _sauvegarder(cache: dict, chemin: Path) -> None:
    tmp = chemin.with_suffix(".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False)
    os.replace(tmp, chemin)


def depuis_cache(
    question: str,
    collection: str,
    formation_code: str | None = None,
    session_id: str | None = None,
) -> dict[str, Any] | None:
    """Retourne la réponse mise en cache ou None (TTL expiré ou absente)."""
    chemin = _chemin_cache()
    cache = _charger(chemin)
    cle = _cle(question, collection, formation_code, session_id)
    entree = cache.get(cle)
    if not entree:
        return None
    if time.time() - entree.get("ts", 0) > TTL_SECONDES:
        cache.pop(cle, None)
        _sauvegarder(cache, chemin)
        logger.debug("🗑️ Cache réponse expiré pour '%s'", question[:50])
        return None
    logger.info("⚡ Cache réponse hit pour '%s'", question[:60])
    return entree["data"]


def mettre_en_cache(
    question: str,
    collection: str,
    data: dict[str, Any],
    formation_code: str | None = None,
    session_id: str | None = None,
) -> None:
    """Stocke une réponse LLM. Purge les entrées les plus anciennes si MAX_ENTREES dépassé."""
    chemin = _chemin_cache()
    cache = _charger(chemin)
    cle = _cle(question, collection, formation_code, session_id)
    cache[cle] = {"ts": time.time(), "data": data, "question": question[:100]}

    if len(cache) > MAX_ENTREES:
        # LRU : supprimer les entrées les plus anciennes
        triees = sorted(cache.items(), key=lambda x: x[1].get("ts", 0))
        for k, _ in triees[:len(cache) - MAX_ENTREES]:
            cache.pop(k, None)

    _sauvegarder(cache, chemin)


def stats() -> dict[str, Any]:
    """Retourne les statistiques du cache : taille, oldest/newest, TTL."""
    chemin = _chemin_cache()
    cache = _charger(chemin)
    now = time.time()
    valides = {k: v for k, v in cache.items() if now - v.get("ts", 0) <= TTL_SECONDES}
    expires = len(cache) - len(valides)
    timestamps = [v["ts"] for v in valides.values()]
    return {
        "entrees_valides": len(valides),
        "entrees_expirees": expires,
        "ttl_secondes": TTL_SECONDES,
        "max_entrees": MAX_ENTREES,
        "plus_ancienne_s": round(now - min(timestamps)) if timestamps else None,
        "plus_recente_s": round(now - max(timestamps)) if timestamps else None,
        "questions_recentes": [v.get("question", "") for v in sorted(valides.values(), key=lambda x: x["ts"], reverse=True)[:5]],
    }


def vider_cache() -> int:
    """Supprime toutes les entrées. Retourne le nombre supprimé."""
    chemin = _chemin_cache()
    cache = _charger(chemin)
    n = len(cache)
    _sauvegarder({}, chemin)
    return n
