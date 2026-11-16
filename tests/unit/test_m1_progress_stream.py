"""SSE réel : progression immédiate, annulation et ordre des cartes existantes."""
import asyncio
import json

import pytest

from app.api.v1 import routes_veille
from app.services.veille.progress_service import PROGRESS_CALLBACK, emit_progress


@pytest.fixture(autouse=True)
def real_stream(monkeypatch):
    monkeypatch.setattr(routes_veille, "DEMO_MODE", False)
    monkeypatch.setattr(routes_veille.tavily_quota_service, "plafond_dur_atteint", lambda: False)


def payload(event):
    return json.loads(event.split("data: ", 1)[1])


def test_etape_visible_avant_la_fin_du_traitement(monkeypatch):
    async def scenario():
        release = asyncio.Event()
        async def detect(*args, **kwargs):
            await emit_progress("requete", "collection_started", "Recherche institutionnelle en cours")
            await release.wait()
            return {"status": "no_results", "opportunities": [], "statistics": {}}
        monkeypatch.setattr(routes_veille.auto_detection, "executer_detection", detect)
        stream = routes_veille._stream_detection(40, 20, False)
        assert "event: debut" in await anext(stream)
        progress = await asyncio.wait_for(anext(stream), 2)
        assert payload(progress)["stage"] == "collection_started"
        assert not release.is_set()
        release.set()
        remaining = [event async for event in stream]
        assert "event: fin" in remaining[-1]
        assert PROGRESS_CALLBACK.get() is None
    asyncio.run(scenario())


def test_fermeture_client_annule_le_traitement(monkeypatch):
    async def scenario():
        cancelled = asyncio.Event()
        async def detect(*args, **kwargs):
            try:
                await emit_progress("analyse", "collection_started", "Collecte")
                await asyncio.Event().wait()
            finally:
                cancelled.set()
        monkeypatch.setattr(routes_veille.auto_detection, "executer_detection", detect)
        stream = routes_veille._stream_detection(40, 20, False)
        await anext(stream)
        await anext(stream)
        await stream.aclose()
        assert cancelled.is_set()
    asyncio.run(scenario())


def test_file_progression_drainee_et_resultats_ordonnes_pour_frontend_existant(monkeypatch):
    async def detect(*args, **kwargs):
        for index in range(30):
            await emit_progress("analyse", "source_collected", f"Source {index}")
        return {"status": "success", "opportunities": [
            {"title": "Moyenne", "score": 50, "ai_recommendation": "Examiner les conditions"},
            {"title": "Prioritaire", "score": 80, "ai_recommendation": "Vérifier l'éligibilité"}], "statistics": {}}
    monkeypatch.setattr(routes_veille.auto_detection, "executer_detection", detect)
    async def collect():
        return [event async for event in routes_veille._stream_detection(40, 20, False)]
    events = asyncio.run(asyncio.wait_for(collect(), 3))
    messages = [payload(event) for event in events if "data: " in event]
    assert sum(m.get("stage") == "source_collected" for m in messages) == 30
    cards = [payload(e) for e in events if e.startswith("event: opportunite\n")]
    assert [card["score"] for card in cards] == [50, 80]
    assert all(card["ai_recommendation"] for card in cards)
    assert [item["score"] for item in messages[-1]["opportunites"]] == [80, 50]
