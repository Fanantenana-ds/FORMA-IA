"""Régressions des essais FID et privés du 30/10 ; aucun réseau ni LLM réel."""
import asyncio
from datetime import UTC, datetime
from unittest.mock import AsyncMock

import httpx
import pytest

from app.services.veille.evidence_service import deadline_details
from app.services.veille.notice_resolution_service import NoticeResolver, deduplicate_notices, parse_notice_page
from app.services.veille.source_registry import SEARCH_GROUP, load_registry
from app.services.veille.tavily_service import SearchResults, TavilyService


def test_html_liens_annonces_et_contenu_principal_sans_encarts():
    document = """<html><header>menu</header><main><article><header><h1>Formation intelligence artificielle</h1></header>
    <p>FID cherche un cabinet pour former ses agents à Madagascar.</p>
    <a href='/recrutement-formation-ia/'>Recrutement cabinet formation intelligence artificielle</a>
    <div class='related-posts'>Autre marché clos</div><footer>Footer</footer></article></main></html>"""
    page = parse_notice_page(document, "https://www.fid.mg/appels-doffres")
    assert page["title"] == "Formation intelligence artificielle"
    assert "Autre marché" not in page["content"]
    assert "menu" not in page["content"]
    assert page["links"][0]["url"] == "https://www.fid.mg/recrutement-formation-ia/"
    assert page["published_at"] is None


def test_liste_fid_resolue_en_annonce_sans_groq(monkeypatch):
    resolver = NoticeResolver(load_registry())
    listing = {"title": "Appels d'offres", "url": "https://www.fid.mg/appels-doffres", "content": "Liste"}
    link = {"title": "Formation IA", "url": "https://www.fid.mg/recrutement-formation-ia"}
    fetch = AsyncMock(side_effect=[({"links": [link]}, listing["url"]), (
        {"title": "Recrutement cabinet formation intelligence artificielle", "published_at": "2026-10-16",
         "content": "FID Madagascar. Formation intelligence artificielle. " * 5}, link["url"])])
    monkeypatch.setattr(resolver, "_fetch", fetch)
    result = asyncio.run(resolver.resolve([listing]))
    assert result[0]["url"] == link["url"]
    assert result[0]["listing_url"] == listing["url"]
    assert result[0]["last_verified_at"]
    assert result[0]["verification_method"] == "direct_public_page"
    assert fetch.await_count == 2


def test_echec_resolution_garde_la_liste_comme_source_non_verifiee(monkeypatch):
    resolver = NoticeResolver(load_registry())
    source = {"title": "Liste", "url": "https://www.fid.mg/appels-doffres", "content": "Liste"}
    monkeypatch.setattr(resolver, "_fetch", AsyncMock(side_effect=httpx.ConnectError("réseau")))
    assert asyncio.run(resolver.resolve([source])) == [source]
    assert resolver.diagnostics[0]["status"] == "failed"
    assert not resolver.allowed("http://127.0.0.1/admin")
    assert not resolver.allowed("https://www.fid.mg.evil.test/annonce")
    assert not resolver.allowed("https://linkedin.com/jobs/view/1")


def test_annonce_individuelle_lue_avant_ancienne_page_paginee(monkeypatch):
    resolver = NoticeResolver(load_registry())
    old = {"title": "Appels d'offres", "url": "https://fid.mg/appels-doffres?_page=70", "content": "Liste ancienne"}
    source = {"title": "Recrutement cabinet formation intelligence artificielle", "url": "https://fid.mg/recrutement-formation-ia", "content": "Extrait tronqué"}
    fetch = AsyncMock(return_value=({"title": source["title"], "content": "FID Madagascar. Besoin de formation IA. " * 6, "published_at": None}, source["url"]))
    monkeypatch.setattr(resolver, "_fetch", fetch)
    result = asyncio.run(resolver.resolve([old, source], "formation intelligence artificielle"))
    assert fetch.await_count == 1
    assert fetch.call_args.args[0] == source["url"]
    assert result[0]["verification_method"] == "direct_public_page"


def test_dedup_reference_et_url_sans_supprimer_autres_avis():
    sources = [{"title": "Formation IA", "url": "https://www.fid.mg/a/", "content": "N°59/AMI/FID/26 Avis IA"},
               {"title": "Formation IA", "url": "https://fid.mg/a?utm_source=index", "content": "N°59/AMI/FID/26 Avis IA"},
               {"title": "Autre publication du même avis", "url": "https://www.fid.mg/b", "content": "N°59/AMI/FID/26 Avis IA"},
               {"title": "Formation web", "url": "https://www.fid.mg/c", "content": "N°60/AMI/FID/26 Avis web"}]
    assert len(deduplicate_notices(sources)) == 2


def test_listes_avec_meme_debut_et_avis_differents_ne_sont_pas_fusionnees():
    from app.services.veille.prefilter_service import _dedupe
    prefix = "En-tête commun des avis publics " * 12
    sources = [{"title": "Appels d'offres", "url": "https://fid.mg/appels-doffres?p=1", "content": prefix + "Formation IA"},
               {"title": "Appels d'offres", "url": "https://fid.mg/appels-doffres?p=2", "content": prefix + "Formation web"}]
    assert len(_dedupe(sources)) == 2


@pytest.mark.parametrize("utc_now, expected, need_time", [
    (datetime(2026, 10, 29, 21, 30, tzinfo=UTC), "bientôt_clôturée", True),
    (datetime(2026, 10, 30, 21, 30, tzinfo=UTC), "expirée", False),
])
def test_date_seule_interpretee_a_madagascar(utc_now, expected, need_time):
    state = deadline_details("2026-10-30", "30 Octobre 2026", {"url": "https://fid.mg/avis", "content": "Date : 30 Octobre 2026"}, utc_now)
    assert state["freshness_status"] == expected
    assert state["needs_closing_time"] is need_time
    assert state["deadline_at"] is None


def test_heure_cloture_16h_et_expiration_meme_jour():
    source = {"url": "https://fid.mg/avis", "content": "Candidature au plus tard le 30 octobre 2026 à 16h00."}
    before = deadline_details("2026-10-30", "30 octobre 2026", source, datetime(2026, 10, 30, 12, tzinfo=UTC))
    after = deadline_details("2026-10-30", "30 octobre 2026", source, datetime(2026, 10, 30, 13, 1, tzinfo=UTC))
    assert before["deadline_at"] == "2026-10-30T16:00:00+03:00"
    assert not before["needs_closing_time"]
    assert after["freshness_status"] == "expirée"


def test_repli_cible_asako_et_portaljob_sans_analyses_llm_supplementaires(monkeypatch):
    from app.services.veille import tavily_service as module
    monkeypatch.setattr(module, "TAVILY_API_KEY", "fake")
    monkeypatch.setattr(module.tavily_quota_service, "plafond_dur_atteint", lambda: False)
    service = TavilyService()
    monkeypatch.setattr(service, "_get_from_cache", lambda q: None)
    linkedin = {"title": "Formateur informatique freelance Madagascar", "url": "https://mg.linkedin.com/jobs/view/1", "content": "Recherche formateur informatique externe Madagascar"}
    asako = {**linkedin, "url": "https://asako.mg/emploi/1"}
    request = AsyncMock(side_effect=[httpx.Response(200, json={"results": [linkedin]}),
                                    httpx.Response(200, json={"results": [asako]}),
                                    httpx.Response(200, json={"results": []})])
    monkeypatch.setattr(service, "_do_request", request)
    token = SEARCH_GROUP.set("missions_privees")
    try:
        result = asyncio.run(service.search("recherche formateur externe informatique Madagascar"))
    finally:
        SEARCH_GROUP.reset(token)
    assert isinstance(result, SearchResults)
    assert len(result) == 2
    assert [call.args[0]["include_domains"] for call in request.call_args_list[1:]] == [["asako.mg"], ["portaljob-madagascar.com"]]
    assert result.diagnostics["domain_coverage"][-1]["status"] == "no_indexed_result"


def test_timeout_de_tentative_borne_toutes_les_phases_http(monkeypatch):
    from app.services.veille import tavily_service as module
    from app.services.veille.tavily_service import TavilySearchError
    monkeypatch.setattr(module, "TAVILY_API_KEY", "fake")
    monkeypatch.setattr(module.tavily_quota_service, "plafond_dur_atteint", lambda: False)
    monkeypatch.setattr(module.tavily_quota_service, "enregistrer_appel", lambda category: None)
    class BlockedClient:
        async def __aenter__(self):
            return self
        async def __aexit__(self, *args):
            return False
        async def post(self, *args, **kwargs):
            await asyncio.sleep(10)
    monkeypatch.setattr(httpx, "AsyncClient", lambda **kwargs: BlockedClient())
    service = TavilyService()
    service.registry.group("institutionnel").request_timeout_seconds = 0.01
    monkeypatch.setattr(service, "_get_from_cache", lambda q: None)
    with pytest.raises(TavilySearchError):
        asyncio.run(service.search("formation IA"))


def test_diagnostic_de_toutes_familles_et_statut_partial_non_technical(monkeypatch):
    from app.orchestrator.veille_orchestrator import VeilleOrchestrator
    orch = VeilleOrchestrator()
    seen = []
    async def analyze(*args, **kwargs):
        seen.append(SEARCH_GROUP.get())
        return {"status": "partial", "opportunities": [], "to_review_candidates": [{"url": "https://fid.mg/avis"}]}
    monkeypatch.setattr(orch, "analyser_opportunites", analyze)
    result = asyncio.run(orch.detecter_automatiquement(["q"] * 4, sync_backend=False))
    assert seen == ["institutionnel", "missions_privees", "international", "decouverte"]
    assert result["status"] == "partial"
    assert all(g["executed"] for g in result["source_groups"])


def test_scoring_reel_ne_penalise_pas_une_cloture_a_16h_comme_expiree_a_minuit(monkeypatch):
    from app.orchestrator import veille_orchestrator as module
    from app.services.veille import evidence_service
    class Frozen(datetime):
        @classmethod
        def now(cls, tz=None):
            value = cls(2026, 10, 30, 0, 30, tzinfo=UTC)
            return value.astimezone(tz) if tz else value.replace(tzinfo=None)
    monkeypatch.setattr(module, "datetime", Frozen)
    monkeypatch.setattr(evidence_service, "datetime", Frozen)
    need = "Recrutement d'un cabinet de formation en intelligence artificielle"
    source = {"title": need, "url": "https://fid.mg/recrutement-formation-ia", "last_verified_at": "2026-10-30T00:29:00+00:00",
              "verification_method": "direct_public_page", "content": f"FID Madagascar. {need}. Candidature le 30 octobre 2026 à 16h00."}
    candidate = {"title": need, "url": source["url"], "source": "FID", "organizer": "FID", "confidence": 0.95,
                 "is_actionable": True, "deadline": "2026-10-30", "domain": "ia", "summary": source["content"],
                 "evidence": {"need": need, "organizer": "FID", "location": "Madagascar", "deadline": "30 octobre 2026"}}
    orch = module.VeilleOrchestrator()
    monkeypatch.setattr(orch.tavily_service, "search", AsyncMock(return_value=[source]))
    monkeypatch.setattr(orch.llm_service, "analyze", AsyncMock(return_value={"opportunities": [candidate]}))
    result = asyncio.run(orch.analyser_opportunites("formation IA", sync_backend=False))
    assert result["total"] == 1
    assert result["opportunities"][0]["deadline_at"] == "2026-10-30T16:00:00+03:00"
    assert result["opportunities"][0]["last_verified_at"] == source["last_verified_at"]
    assert "expirée" not in result["opportunities"][0]["reason"]
