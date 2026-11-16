"""Preuves FID et collecte avant analyse : régressions du diagnostic all."""
import asyncio
import json
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock

import pytest

from app.orchestrator.veille_orchestrator import VeilleOrchestrator
from app.services.llm import LLMRateLimitError
from app.services.veille.evidence_service import qualify_candidate
from app.services.veille.evidence_service import source_closing_date
from app.services.veille.llm_analysis_service import LLMAnalysisService
from app.services.veille.source_registry import SEARCH_GROUP
from app.services.veille.tavily_service import SearchResults
from app.services.veille.notice_resolution_service import NoticeResolver
from app.services.veille.source_registry import load_registry


def source_and_candidate():
    day = (datetime.now(UTC) + timedelta(days=5)).date().isoformat()
    need = "Recrutement d'un cabinet pour la formation en intelligence artificielle"
    source = {"title": need, "url": "https://fid.mg/recrutement-formation-ia", "search_group": "institutionnel",
              "content": f"{need}. FID Madagascar. Date limite : {day}.",
              "verification_method": "direct_public_page", "last_verified_at": datetime.now(UTC).isoformat()}
    candidate = {"title": need, "url": source["url"], "source": "FID", "organizer": "FID", "domain": "ia",
                 "is_actionable": True, "summary": source["content"], "confidence": 0.95, "deadline": day,
                 "evidence": {"need": "Reformulation inventée par le modèle", "organizer": "FID", "location": "Madagascar", "deadline": day}}
    return source, candidate


def test_citation_besoin_invalide_remplacee_par_titre_effectivement_lu():
    source, candidate = source_and_candidate()
    result, gaps = qualify_candidate(candidate, [source])
    assert gaps == []
    assert result["evidence"]["need"] == source["title"]
    assert result["evidence_origin"]["need"] == "direct_source_heading"


def test_organisme_et_cloture_omis_par_modele_retrouves_dans_le_corps_lu():
    source, candidate = source_and_candidate()
    candidate["evidence"] = {}
    candidate["deadline"] = None
    result, gaps = qualify_candidate(candidate, [source])
    assert gaps == []
    assert result["evidence"]["organizer"] == "FID"
    assert result["evidence_origin"]["organizer"] == "direct_source_match"
    assert result["evidence_origin"]["deadline"] == "direct_closing_clause"


def test_citation_presente_mais_mauvais_champ_organisme_corrigee():
    source, candidate = source_and_candidate()
    candidate["evidence"]["organizer"] = source["title"]
    result, gaps = qualify_candidate(candidate, [source])
    assert gaps == []
    assert result["evidence"]["organizer"] == "FID"


def test_publication_ne_devient_pas_cloture_et_dates_contradictoires_restent_a_confirmer():
    assert source_closing_date({"content": "Publié le 16 octobre 2026"}) == (None, None)
    assert source_closing_date({"content": "Date de clôture : 30 octobre 2026. Date limite : 31 octobre 2026."}) == (None, None)


@pytest.mark.parametrize("kind", ["snippet", "advertisement", "invented_heading"])
def test_repli_preuve_ne_promet_pas_une_annonce_non_verifiee(kind):
    source, candidate = source_and_candidate()
    if kind == "snippet":
        source.pop("last_verified_at")
    elif kind == "advertisement":
        source["title"] = "Formation intelligence artificielle : inscrivez-vous"
        source["content"] = source["title"]
    else:
        source["content"] = "Une page sans besoin identifiable."
    result, gaps = qualify_candidate(candidate, [source])
    assert gaps and not result["is_actionable"]
    assert "need" not in result["evidence"]


def test_prompt_compact_reduit_et_garde_les_extraits_de_cloture():
    service = LLMAnalysisService()
    source, _ = source_and_candidate()
    compact, submitted = service._prepare_compact_prompt("formation IA", [source])
    full = service._build_prompt("formation IA", [source])
    assert len(compact) < len(full)
    assert submitted == [source]
    assert source["title"] in compact and "Date limite" in compact


def test_retry_429_court_borne_sans_retry_global(monkeypatch):
    from app.services.veille import llm_analysis_service as module
    service = LLMAnalysisService()
    failure = LLMRateLimitError("Please try again in 134.999999ms.")
    service.llm = AsyncMock()
    service.llm.generate.side_effect = [failure, {"content": json.dumps({"opportunities": []})}]
    sleep = AsyncMock()
    monkeypatch.setattr(module.asyncio, "sleep", sleep)
    result = asyncio.run(service.analyze("formation IA", [], compact=True))
    assert result["opportunities"] == []
    assert service.llm.generate.await_count == 2
    assert 0.28 < sleep.call_args.args[0] < 0.30
    service.llm.generate_with_retry.assert_not_awaited()


def test_second_429_ne_declenche_pas_de_troisieme_appel(monkeypatch):
    from app.services.veille import llm_analysis_service as module
    service = LLMAnalysisService()
    service.llm = AsyncMock()
    service.llm.generate.side_effect = LLMRateLimitError("Please try again in 1ms.")
    monkeypatch.setattr(module.asyncio, "sleep", AsyncMock())
    assert asyncio.run(service.analyze("q", []))["status"] == "quota_atteint"
    assert service.llm.generate.await_count == 2


def test_toutes_les_familles_collectees_avant_un_seul_lot_groq(monkeypatch):
    orch = VeilleOrchestrator()
    source, candidate = source_and_candidate()
    seen = []
    async def search(*args, **kwargs):
        seen.append(SEARCH_GROUP.get())
        return SearchResults([source], {})
    async def analyze(*args, **kwargs):
        assert len(seen) == 4
        assert kwargs["compact"] is True
        return {"opportunities": [candidate]}
    monkeypatch.setattr(orch.tavily_service, "search", search)
    model = AsyncMock(side_effect=analyze)
    monkeypatch.setattr(orch.llm_service, "analyze", model)
    result = asyncio.run(orch.detecter_automatiquement(["formation IA"] * 4, sync_backend=False, collect_first=True))
    assert seen == ["institutionnel", "missions_privees", "international", "decouverte"]
    assert model.await_count == 1
    assert result["total"] == 1
    assert result["collection_complete"] is True
    assert all(g["executed"] for g in result["source_groups"])


def test_quota_groq_n_empeche_plus_la_collecte_decouverte(monkeypatch):
    orch = VeilleOrchestrator()
    source, _ = source_and_candidate()
    search = AsyncMock(return_value=SearchResults([source], {}))
    monkeypatch.setattr(orch.tavily_service, "search", search)
    model = AsyncMock(return_value={"status": "quota_atteint", "opportunities": []})
    monkeypatch.setattr(orch.llm_service, "analyze", model)
    result = asyncio.run(orch.detecter_automatiquement(["q"] * 4, sync_backend=False, collect_first=True))
    assert search.await_count == 4
    assert result["status"] == "quota_atteint"
    assert result["collection_complete"] is True


def test_pages_generales_ne_consomment_aucun_appel_groq(monkeypatch):
    orch = VeilleOrchestrator()
    pages = [{"title": "PortalJob", "url": "https://portaljob-madagascar.com", "content": "Portail emploi Madagascar"},
             {"title": "Asako informatique", "url": "https://asako.mg/emploi/s-informatique-digital", "content": "Liste"}]
    model = AsyncMock()
    monkeypatch.setattr(orch.llm_service, "analyze", model)
    result = asyncio.run(orch.analyser_opportunites("formation", sync_backend=False, collected_sources=pages))
    assert len(result["navigation_sources"]) == 2
    model.assert_not_awaited()


def test_index_courant_lu_avant_ancien_avis_peu_lie_a_la_requete(monkeypatch):
    resolver = NoticeResolver(load_registry())
    old = {"title": "Cabinet formation sécurité informatique ISO 27001", "url": "https://fid.mg/formation-securite-2025", "content": "Ancien avis"}
    current = {"title": "Appels à manifestations d'intérêts", "url": "https://fid.mg/appels-a-manifestations-dinterets", "content": "Index actuel"}
    target = "https://fid.mg/recrutement-formation-intelligence-artificielle"
    fetch = AsyncMock(side_effect=[({"links": [{"title": "Recrutement formation intelligence artificielle", "url": target}]}, current["url"]),
                                  ({"title": "Recrutement formation intelligence artificielle", "published_at": None,
                                    "content": "Besoin de formation IA pour le FID Madagascar. " * 5}, target)])
    monkeypatch.setattr(resolver, "_fetch", fetch)
    result = asyncio.run(resolver.resolve([old, current], "formation informatique intelligence artificielle Madagascar"))
    assert fetch.call_args_list[0].args[0] == current["url"]
    assert result[0]["url"] == target
