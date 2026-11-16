"""Qualité des décisions et collecte concurrente bornée ; aucun réseau réel."""
import asyncio
from unittest.mock import AsyncMock

import httpx
import pytest

from app.orchestrator.veille_orchestrator import VeilleOrchestrator
from app.services.veille.prefilter_service import navigation_reason, rejection_reason
from app.services.veille.source_registry import SEARCH_GROUP
from app.services.veille.tavily_service import SearchResults, TavilySearchError, TavilyService
from tests.unit.test_m1_collect_first import source_and_candidate


def test_concurrence_bornee_a_deux_familles_et_contexte_isole(monkeypatch):
    orch = VeilleOrchestrator()
    source, candidate = source_and_candidate()
    active, peak, groups = 0, 0, []
    async def search(*args, **kwargs):
        nonlocal active, peak
        group = SEARCH_GROUP.get()
        active += 1
        peak = max(peak, active)
        groups.append(group)
        await asyncio.sleep(0.02)
        assert SEARCH_GROUP.get() == group
        active -= 1
        return SearchResults([{**source, "search_group": group}], {})
    monkeypatch.setattr(orch.tavily_service, "search", search)
    model = AsyncMock(return_value={"opportunities": [candidate]})
    monkeypatch.setattr(orch.llm_service, "analyze", model)
    result = asyncio.run(orch.detecter_automatiquement(["formation"] * 4, sync_backend=False, collect_first=True))
    assert peak == 2 and len(set(groups)) == 4
    assert model.await_count == 1
    assert result["total"] == 1


@pytest.mark.parametrize("reason", ["Contient une formation web et PAO, hors IA", "Publication LinkedIn, pas d'appel d'offres officiel"])
def test_rejet_insuffisant_passe_a_verifier_sans_fausse_confirmation(monkeypatch, reason):
    orch = VeilleOrchestrator()
    source = {"title": "Recherche formateur web PAO externe", "url": "https://asako.mg/annonces/1", "content": "Besoin de formation web externe Madagascar"}
    monkeypatch.setattr(orch.llm_service, "analyze", AsyncMock(return_value={"opportunities": [], "rejets": [{"resultat": 1, "raison": reason}]}))
    result = asyncio.run(orch.analyser_opportunites("formation IA", sync_backend=False, collected_sources=[source]))
    assert result["total"] == 0
    assert result["to_review_candidates"][0]["review_reason"] == "unsupported_rejection"
    assert result["analyzed_sources"][0]["final_status"] == "to_review"


def test_seuil_final_recalcule_compteurs_et_decision_source(monkeypatch):
    orch = VeilleOrchestrator()
    source, candidate = source_and_candidate()
    monkeypatch.setattr(orch.tavily_service, "search", AsyncMock(return_value=[source]))
    monkeypatch.setattr(orch.llm_service, "analyze", AsyncMock(return_value={"opportunities": [candidate]}))
    result = asyncio.run(orch.detecter_automatiquement(["formation IA"], min_score=100, sync_backend=False, collect_first=True))
    assert result["total"] == 0
    assert result["statistics"]["below_requested_score"] == 1
    assert result["statistics"]["madagascar"] == 0
    assert result["analyzed_sources"][0]["final_status"] == "filtered_score"


def test_bruit_explicite_ecarte_sans_eliminer_les_annonces_pao():
    assert navigation_reason({"url": "https://asako.mg/blog/metiers/test"})
    assert navigation_reason({"url": "https://fr.linkedin.com/jobs/formation-ia-emplois"})
    assert rejection_reason({"title": "Notice Of Sale Four Motorcycles"})
    assert rejection_reason({"title": "Formation Restauration et Patisserie Guinée"})
    assert not navigation_reason({"url": "https://asako.mg/annonces/formateur-pao-123"})
    assert not rejection_reason({"title": "Recrutement institut formation web et PAO Madagascar"})


def test_erreurs_http_conservent_les_tentatives(monkeypatch):
    from app.services.veille import tavily_service as module
    monkeypatch.setattr(module, "TAVILY_API_KEY", "fake")
    monkeypatch.setattr(module.tavily_quota_service, "plafond_dur_atteint", lambda: False)
    monkeypatch.setattr(module.tavily_quota_service, "enregistrer_appel", lambda category: None)
    class FailedClient:
        async def __aenter__(self): return self
        async def __aexit__(self, *args): return False
        async def post(self, *args, **kwargs): raise httpx.ConnectError("DNS")
    monkeypatch.setattr(httpx, "AsyncClient", lambda **kwargs: FailedClient())
    service = TavilyService()
    monkeypatch.setattr(service, "_get_from_cache", lambda query: None)
    with pytest.raises(TavilySearchError) as failure:
        asyncio.run(service.search("formation"))
    attempts = failure.value.diagnostics["attempts"]
    assert len(attempts) == 2
    assert all(a["reason"] == "ConnectError" for a in attempts)
