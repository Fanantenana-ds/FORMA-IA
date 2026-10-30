"""Contrat M1 réel : registre, preuves et séparation des candidats."""
import asyncio
from copy import deepcopy
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock

import pytest
import httpx

from app.orchestrator.veille_orchestrator import VeilleOrchestrator
from app.services.veille.evidence_service import qualify_candidate
from app.services.veille.source_registry import SEARCH_GROUP, load_registry
from app.services.veille.tavily_service import TavilyService


def documented():
    day = (datetime.now(UTC) + timedelta(days=20)).date().isoformat()
    need = "Recrutement d'un cabinet de formation en intelligence artificielle et data"
    source = {"title": need, "url": "https://www.fid.mg/avis-ia",
              "content": f"FID, Madagascar. {need}. Date limite : {day}.",
              "published_at": "2026-10-16", "captured_at": datetime.now(UTC).isoformat()}
    candidate = {"title": need, "url": source["url"], "organizer": "FID", "source": "FID",
                 "summary": source["content"], "confidence": 0.95, "domain": "ia",
                 "opportunity_type": "appel_offres", "is_actionable": True, "deadline": day,
                 "evidence": {"need": need, "organizer": "FID", "location": "Madagascar",
                              "deadline": f"Date limite : {day}"}}
    return source, candidate


def test_registre_complete_la_liste_env_et_filtre_effectivement(monkeypatch):
    monkeypatch.setenv("TAVILY_INCLUDE_DOMAINS", "afd.fr,asako.mg")
    monkeypatch.setenv("TAVILY_EXCLUDE_DOMAINS", "exclu.mg")
    monkeypatch.setenv("TAVILY_REJECTED_KEYWORDS", "unicef,parasite-test")
    monkeypatch.setenv("TAVILY_JOB_KEYWORDS", "mission-partenaire")
    registry = load_registry()
    assert {"fid.mg", "linkedin.com", "portaljob-madagascar.com"}.issubset(registry.domains())
    assert "unicef" not in registry.rejected_keywords
    assert "parasite-test" in registry.rejected_keywords
    assert "mission-partenaire" in registry.employment_keywords
    assert not registry.allowed_url("https://exclu.mg/offre")
    assert not registry.allowed_url("https://www.linkedin.com/in/profil")
    assert registry.allowed_url("https://fr.linkedin.com/posts/offre")
    assert not registry.allowed_url("https://portaljob-madagascar.com/candidats/view/1")
    assert not registry.allowed_url("https://afd.fr/fr/ressources/rapport")


def test_registre_invalide_refuse_au_chargement(tmp_path):
    config = tmp_path / "invalid.yaml"
    config.write_text("version: 1\ngroups: []", encoding="utf-8")
    with pytest.raises(ValueError):
        load_registry(config)


def test_faux_positif_de_la_page_acheteur_ne_peut_pas_etre_confirme():
    source = {"title": "AFD - Oct 28, 2026", "content": "Oct 28, 2026",
              "url": "https://afd.dgmarket.com/tenders/adminShowBuyer.do?buyerId=1#avis-1"}
    _, candidate = documented()
    candidate.update(url=source["url"], title="Appel d'offres formation informatique Madagascar")
    result, gaps = qualify_candidate(candidate, [source])
    assert gaps
    assert not result["is_actionable"]
    assert result["status"] == "to_review"
    assert result["deadline"] is None
    assert result["last_verified_at"] is None
    assert result["next_step"] == "verify_source"


def test_preuves_exactes_et_metadonnees_source_preservees():
    source, candidate = documented()
    candidate.update(published_at="2099-01-01", budget="50 millions Ar")
    result, gaps = qualify_candidate(candidate, [source])
    assert gaps == []
    assert result["published_at"] == source["published_at"]
    assert result["captured_at"] == source["captured_at"]
    assert result["budget"] == "Non précisé"
    assert result["verification_status"] == "documented"
    assert result["last_verified_at"] is None
    assert result["ai_risk_level"] != "faible"


def test_url_inventee_localisation_inventee_et_echeance_absente_restent_a_verifier():
    source, candidate = documented()
    candidate["url"] = "https://inventee.mg/annonce"
    result, gaps = qualify_candidate(candidate, [source])
    assert gaps and not result["is_actionable"]
    source, candidate = documented()
    candidate["evidence"]["location"] = "Antananarivo inventé"
    source["url"] = candidate["url"] = "https://www.ungm.org/Public/Notice/1"
    candidate["deadline"] = None
    result, gaps = qualify_candidate(candidate, [source])
    assert any("Localisation" in g for g in gaps)
    assert any("Échéance" in g for g in gaps)
    assert "vérifier" in result["ai_recommendation"]


def test_parcours_reel_sans_double_du_controle_des_preuves(monkeypatch):
    source, candidate = documented()
    orch = VeilleOrchestrator()
    monkeypatch.setattr(orch.tavily_service, "search", AsyncMock(return_value=[source]))
    monkeypatch.setattr(orch.llm_service, "analyze", AsyncMock(return_value={"opportunities": [candidate]}))
    result = asyncio.run(orch.analyser_opportunites("formation IA", sync_backend=False))
    assert result["total"] == 1
    assert result["opportunities"][0]["evidence"]["need"] == candidate["evidence"]["need"]
    assert result["opportunities"][0]["last_verified_at"] is None
    assert result["statistics"]["backend_sync"]["sent"] == 0
    assert result["opportunities"][0]["confidence"] == candidate["confidence"]


def test_parcours_reel_candidat_fabrique_jamais_promu(monkeypatch):
    source, candidate = documented()
    source["content"] = "Page générale sans annonce précise."
    source["title"] = "Un portail"
    orch = VeilleOrchestrator()
    monkeypatch.setattr(orch.tavily_service, "search", AsyncMock(return_value=[source]))
    monkeypatch.setattr(orch.llm_service, "analyze", AsyncMock(return_value={"opportunities": [candidate]}))
    result = asyncio.run(orch.analyser_opportunites("formation IA", sync_backend=False))
    assert result["opportunities"] == []
    assert len(result["to_review_candidates"]) == 1
    assert result["analyzed_sources"][0]["final_status"] == "to_review"


def test_cache_separe_les_familles_et_la_configuration():
    service = TavilyService()
    first = service._cache_key("formation IA")
    token = SEARCH_GROUP.set("missions_privees")
    try:
        assert service._cache_key("formation IA") != first
    finally:
        SEARCH_GROUP.reset(token)
    service.registry.excluded_domains.append("ajoute.mg")
    assert service._cache_key("formation IA") != first


def test_requete_privee_utilise_effectivement_les_domaines_et_exclusions(monkeypatch):
    from app.services.veille import tavily_service as module
    monkeypatch.setattr(module, "TAVILY_API_KEY", "fake")
    monkeypatch.setattr(module.tavily_quota_service, "plafond_dur_atteint", lambda: False)
    service = TavilyService()
    monkeypatch.setattr(service, "_get_from_cache", lambda query: None)
    source = {"title": "Recherche formateur informatique freelance", "url": "https://www.asako.mg/emploi/1",
              "content": "Une entreprise cherche un prestataire pour une formation informatique à Madagascar"}
    request = AsyncMock(return_value=httpx.Response(200, json={"results": [source]}))
    monkeypatch.setattr(service, "_do_request", request)
    token = SEARCH_GROUP.set("missions_privees")
    try:
        result = asyncio.run(service.search("formation informatique"))
    finally:
        SEARCH_GROUP.reset(token)
    # La première requête couvre la famille ; les suivantes ciblent les sites
    # absents, sans supposer que Tavily renvoie chaque domaine demandé.
    payload = request.call_args_list[0].args[0]
    assert set(payload["include_domains"]) == {"linkedin.com", "asako.mg", "portaljob-madagascar.com"}
    assert "wikipedia.org" in payload["exclude_domains"]
    assert payload["include_raw_content"] is False
    assert result[0]["employment_signal"] is True


def test_quota_tavily_arrete_sans_repli(monkeypatch):
    from app.services.veille import tavily_service as module
    from app.services.veille.tavily_quota_service import QuotaTavilyDepasseError
    monkeypatch.setattr(module, "TAVILY_API_KEY", "fake")
    monkeypatch.setattr(module.tavily_quota_service, "plafond_dur_atteint", lambda: False)
    service = TavilyService()
    monkeypatch.setattr(service, "_get_from_cache", lambda query: None)
    request = AsyncMock(return_value=httpx.Response(429))
    monkeypatch.setattr(service, "_do_request", request)
    with pytest.raises(QuotaTavilyDepasseError):
        asyncio.run(service.search("formation IA"))
    assert request.await_count == 1
