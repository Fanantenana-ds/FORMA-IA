"""Dernière détection réelle par compte ; contexte factuel de l'assistant."""
import copy
import time
from datetime import datetime
from zoneinfo import ZoneInfo

_results = {}


def remember(owner: str, result: dict):
    now = time.monotonic()
    for key in list(_results):
        if _results[key][0] <= now:
            del _results[key]
    while len(_results) >= 100 and owner not in _results:
        del _results[next(iter(_results))]
    context = {key: copy.deepcopy(result.get(key)) for key in ("status", "opportunities", "statistics", "notes", "to_review_candidates", "pending_sources")}
    context["capture"] = datetime.now(ZoneInfo("Indian/Antananarivo")).isoformat()
    _results[owner] = (now + 3600, context)


def latest(owner: str):
    item = _results.get(owner)
    return copy.deepcopy(item[1]) if item and item[0] > time.monotonic() else None
