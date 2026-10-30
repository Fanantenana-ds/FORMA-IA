"""Régressions issues des journaux M1 du 29/10 ; aucun appel payant."""
import asyncio
from datetime import date, timedelta
from unittest.mock import AsyncMock

from app.services.llm import LLMRateLimitError
from app.services.veille import llm_analysis_service as llm
from app.services.veille.prefilter_service import diversify_sources, rank_results, rejection_reason
from app.services.veille.tavily_service import decouper_liste_avis


def test_institut_formation_web_conserve():
    source = {"title": "Recrutement d'un institut de formation web et PAO",
              "url": "https://www.ungm.org/notice/1",
              "content": "À Madagascar, formation externe pour les agents."}
    assert rank_results([source], "formation informatique") == [source]


def test_sources_inutiles_ne_consument_pas_groq():
    titles = ["Formation au Sénégal", "Fourniture de kits solaires",
              "Recrutement d’un cabinet de macroévaluation"]
    for title in titles:
        assert rejection_reason({"title": title})
    assert not rejection_reason({"title": "Formation informatique pour le ministère de la Santé"})
    assert not rejection_reason({"title": "Formation data Madagascar et Sénégal"})


def test_publication_ancienne_pas_confondue_avec_echeance():
    assert not rejection_reason({"title": "Formation IA", "published_at": "2020-01-01"})
    assert rejection_reason({"deadline": (date.today() - timedelta(days=1)).isoformat()})


def test_diversite_sans_perdre_de_sources_ni_appeler_le_reseau():
    sources = [{"title": title, "url": url} for title, url in [
        ("A", "https://afd.dgmarket.com/1"), ("B", "https://autre.dgmarket.com/2"),
        ("C", "https://www.ungm.org/3"), ("D", "https://armp.mg/4"),
        ("E", "https://ungm.org/5"),
    ]]
    result = diversify_sources(sources)
    assert [r["title"] for r in result] == ["A", "C", "D", "B", "E"]
    assert len(result) == len(sources)
    assert [r["title"] for r in sources] == ["A", "B", "C", "D", "E"]


def test_budget_prompt_compte_uniquement_les_sources_envoyees(monkeypatch):
    instance = service()
    instance.veille_yaml_text = "json {{QUERY}} {{RESULTATS_BRUTS}}"
    sources = [{"title": str(i), "url": f"https://a.mg/{i}", "content": "x" * 100} for i in range(2)]
    maximum = len(instance._build_prompt("q", sources[:1])) + 1
    monkeypatch.setattr(llm, "MAX_PROMPT_CHARS", maximum)
    instance.llm.generate.return_value = {"content": '{"opportunities": [], "rejets": []}'}
    result = asyncio.run(instance.analyze("q", sources))
    assert result["sources_submitted"] == 1
    prompt = instance.llm.generate.call_args.kwargs["user_prompt"]
    assert "RESULTAT 1" in prompt
    assert "RESULTAT 2" not in prompt


def test_liste_conserve_lien_annonce_et_publication():
    today = date(2026, 10, 29)
    raw = ("Avis publiés | Oct 28, 2026 | Appel d'offres | [Formation web Madagascar](/tender/1) "
           "| Oct 29, 2026 | Appel d'offres | [Formation data Madagascar](/tender/2)")
    result = decouper_liste_avis("Liste", "https://d.example/buyer", raw, aujourd_hui=today)
    assert [r["url"] for r in result] == ["https://d.example/tender/1", "https://d.example/tender/2"]
    assert result[0]["title"] == "Formation web Madagascar"
    assert result[0]["published_at"] == "2026-10-28"


def service():
    instance = llm.LLMAnalysisService()
    instance.llm = AsyncMock()
    return instance


def test_429_une_tentative_meme_si_env_retry_global_3(monkeypatch):
    instance = service()
    monkeypatch.setenv("RETRY_MAX_ATTEMPTS", "3")
    instance.llm.generate.side_effect = LLMRateLimitError("quota")
    result = asyncio.run(instance.analyze("formation", []))
    assert result["status"] == "quota_atteint"
    assert instance.llm.generate.await_count == 1
    instance.llm.generate_with_retry.assert_not_awaited()


def test_budget_arrete_un_appel_bloque(monkeypatch):
    instance = service()
    monkeypatch.setattr(llm, "M1_ANALYSIS_BUDGET_S", 0.01)
    async def bloque(**kwargs):
        await asyncio.sleep(10)
    instance.llm.generate.side_effect = bloque
    assert asyncio.run(instance.analyze("formation", [])) is None


def test_demo_ne_fait_aucun_appel_fournisseur(monkeypatch):
    from app.api.v1 import routes_veille
    monkeypatch.setattr(routes_veille, "DEMO_MODE", True)
    fournisseur = AsyncMock(side_effect=AssertionError("Appel réel interdit en démo"))
    monkeypatch.setattr(routes_veille.auto_detection, "executer_detection", fournisseur)
    async def sans_pause(*args):
        pass
    monkeypatch.setattr(routes_veille.asyncio, "sleep", sans_pause)
    async def collecte():
        return [event async for event in routes_veille._stream_detection(40, 20, False)]
    events = asyncio.run(collecte())
    assert any("event: fin" in event for event in events)
    fournisseur.assert_not_awaited()
