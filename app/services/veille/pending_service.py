"""Reprise bornée de sources collectées, sans nouvelle recherche web."""
import copy
import secrets
import time

from fastapi import HTTPException

_runs = {}
TTL = 1800


def save(documents, query, owner=None, min_score=40):
    now = time.monotonic()
    for key in list(_runs):
        if _runs[key]["expires"] <= now:
            del _runs[key]
    if not documents or len(documents) > 200 or sum(len(str(item)) for item in documents) > 4_000_000:
        return None
    while len(_runs) >= 20:
        del _runs[next(iter(_runs))]
    key = secrets.token_urlsafe(32)
    _runs[key] = {"documents": copy.deepcopy(documents), "query": query,
                  "owner": owner, "min_score": min_score, "expires": now + TTL, "busy": False}
    return key


def bind(key, owner, min_score=40):
    if key in _runs and _runs[key]["owner"] is None:
        _runs[key]["owner"] = owner
        _runs[key]["min_score"] = min_score


async def resume(key, owner, orchestrator):
    run = _runs.get(key)
    if not run or run["expires"] <= time.monotonic() or run["owner"] != owner:
        raise HTTPException(410, "Sources indisponibles ou expirées. Relancez la détection.")
    if run["busy"]:
        raise HTTPException(409, "Une analyse de ces sources est déjà en cours.")
    run["busy"] = True
    try:
        import asyncio
        selected = run["documents"][:3]
        async with asyncio.timeout(90):
            result = await orchestrator.analyser_opportunites(run["query"], sync_backend=False, collected_sources=selected)
        pending_urls = {s.get("url") for s in result.get("pending_sources", [])}
        remaining = [s for s in selected if s.get("url") in pending_urls] + run["documents"][3:]
        if not result.get("analyzed_sources"):
            remaining = run["documents"]
        # Le même seuil que la recherche initiale s'applique à la reprise.
        documented = result.get("opportunities", [])
        result["opportunities"] = sorted([o for o in documented if o.get("score", 0) >= run["min_score"]], key=lambda o: o.get("score", 0), reverse=True)
        result["total"] = len(result["opportunities"])
        below_threshold = {o.get("url") for o in documented if o.get("score", 0) < run["min_score"]}
        for source in result.get("analyzed_sources", []):
            if source.get("url") in below_threshold:
                source.update(final_status="filtered_score", final_reason=f"Score inférieur au seuil demandé de {run['min_score']}/100.")
        result["continuation_id"] = save(remaining, run["query"], owner, run["min_score"])
        result["pending_sources"] = [{"title": s.get("title"), "url": s.get("url")} for s in remaining]
        result.setdefault("statistics", {})["sources_unanalyzed"] = len(remaining)
        result["statistics"].update(final=result["total"], final_opportunities=result["total"], confirmed_opportunities=result["total"], below_requested_score=len(documented)-result["total"])
        if remaining and result.get("status") in {"success", "no_results"}:
            result["status"] = "partial"
        _runs.pop(key, None)
        return result
    finally:
        run["busy"] = False
