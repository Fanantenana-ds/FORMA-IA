import asyncio
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException

from app.services.veille import pending_service as pending


@pytest.fixture(autouse=True)
def clear_runs():
    pending._runs.clear()
    yield
    pending._runs.clear()


def test_reprise_conserve_sources_et_seuil_sans_recherche_web():
    documents = [{"url": f"https://example.org/{i}", "title": str(i), "content": "preuve collectée"} for i in range(5)]
    key = pending.save(documents, "formation")
    pending.bind(key, "user", 50)
    analyze = AsyncMock(return_value={"status": "success", "analyzed_sources": documents[:3], "pending_sources": [], "opportunities": [{"score": 49}, {"score": 70}]})
    orchestrator = type("Orchestrator", (), {"analyser_opportunites": analyze})()
    result = asyncio.run(pending.resume(key, "user", orchestrator))
    assert result["total"] == 1
    assert len(result["pending_sources"]) == 2
    assert result["status"] == "partial"
    assert analyze.call_args.kwargs == {"sync_backend": False, "collected_sources": documents[:3]}
    assert key not in pending._runs
    assert pending._runs[result["continuation_id"]]["owner"] == "user"


@pytest.mark.parametrize("case", ["other_user", "expired", "busy"])
def test_reprise_refuse_acces_expiration_et_double_clic(case):
    key = pending.save([{"url": "https://example.org"}], "formation", "user")
    owner = "other" if case == "other_user" else "user"
    if case == "expired": pending._runs[key]["expires"] = 0
    if case == "busy": pending._runs[key]["busy"] = True
    with pytest.raises(HTTPException) as error:
        asyncio.run(pending.resume(key, owner, None))
    assert error.value.status_code == (409 if case == "busy" else 410)


def test_erreur_conserve_la_collecte():
    key = pending.save([{"url": "https://example.org"}], "formation", "user")
    orchestrator = type("Orchestrator", (), {"analyser_opportunites": AsyncMock(side_effect=RuntimeError("quota"))})()
    with pytest.raises(RuntimeError): asyncio.run(pending.resume(key, "user", orchestrator))
    assert not pending._runs[key]["busy"]
    assert len(pending._runs[key]["documents"]) == 1
