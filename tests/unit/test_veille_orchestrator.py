# ============================================================
# TESTS — app/orchestrator/veille_orchestrator.py (M1)
# ============================================================
# Aucun appel réseau réel (Tavily/Groq/Backend) : tout est doublé au niveau
# des services déjà instanciés par l'orchestrateur, comme pour les autres
# orchestrateurs de la suite (tdr_orchestrator, facturation_orchestrator).
# ============================================================

import asyncio

import pytest

import app.services.hitl.hitl_helper as hitl_helper_module
from app.orchestrator import veille_orchestrator as vo_module
from app.orchestrator.veille_orchestrator import VeilleOrchestrator
from app.services.veille.tavily_service import TavilySearchError


def run(coro):
    return asyncio.run(coro)


@pytest.fixture
def orchestrateur(monkeypatch):
    o = VeilleOrchestrator()
    # Ces tests isolent l'orchestration et le post-traitement historique.
    # Les preuves réelles sont couvertes dans test_m1_final.py, sans ce double.
    monkeypatch.setattr(vo_module, "qualify_candidate", lambda item, sources: (item.copy(), []))
    # Doublures par défaut : "aucun résultat" (chaque test les redéfinit au besoin)
    monkeypatch.setattr(o.tavily_service, "search", _async(lambda q, **kw: []))
    monkeypatch.setattr(o.llm_service, "analyze", _async(lambda *a, **k: None))
    monkeypatch.setattr(o.classification_service, "classify", lambda c: {"domain": "ia"})
    monkeypatch.setattr(o.classification_service, "detect_country", lambda c: "Madagascar")
    monkeypatch.setattr(o.scoring_service, "score", lambda c, **kw: {"score": 80, "confidence": 0.9})
    monkeypatch.setattr(
        vo_module, "sync_opportunities_to_backend",
        _async(lambda opps: {"enabled": True, "sent": len(opps), "failed": 0}),
    )
    monkeypatch.setattr(
        vo_module, "sync_new_opportunities_to_backend",
        _async(lambda opps: {"enabled": True, "sent": len(opps), "failed": 0, "already_present": 0}),
    )
    monkeypatch.setattr(
        vo_module, "create_review",
        lambda agent_id, data, summary, criticity: "review-test-001",
    )
    return o


def _async(fn):
    async def wrapper(*args, **kwargs):
        return fn(*args, **kwargs)
    return wrapper


def _opportunite_brute(titre="Formation IA — Appel d'offre"):
    return {"title": titre, "url": "https://example.mg/ao", "content": "Contenu de l'annonce."}


# ---- analyser_opportunites — cas vides ----

def test_analyser_opportunites_query_vide(orchestrateur):
    resultat = run(orchestrateur.analyser_opportunites(""))
    assert resultat["status"] == "error"
    assert resultat["total"] == 0


def test_analyser_opportunites_aucun_resultat_tavily(orchestrateur, monkeypatch):
    monkeypatch.setattr(orchestrateur.tavily_service, "search", _async(lambda q, **kw: []))
    resultat = run(orchestrateur.analyser_opportunites("formation IA"))
    assert resultat["status"] == "no_results"


def test_analyser_opportunites_erreur_tavily_n_est_pas_un_zero(monkeypatch, orchestrateur):
    async def indisponible(*args, **kwargs):
        raise TavilySearchError("DNS impossible")

    monkeypatch.setattr(orchestrateur.tavily_service, "search", indisponible)
    resultat = run(orchestrateur.analyser_opportunites("formation IA"))
    assert resultat["status"] == "technical_error"
    assert resultat["total"] == 0
    assert resultat["statistics"]["source_retrieval_seconds"] >= 0


def test_analyser_opportunites_aucun_resultat_apres_prefiltre(orchestrateur, monkeypatch):
    monkeypatch.setattr(orchestrateur.tavily_service, "search", _async(lambda q, **kw: [_opportunite_brute()]))
    monkeypatch.setattr(vo_module, "rank_results", lambda results, query: [])
    resultat = run(orchestrateur.analyser_opportunites("formation IA"))
    assert resultat["status"] == "no_results"
    assert resultat["statistics"]["raw_results"] == 1


def test_analyser_opportunites_ajoute_contexte_madagascar(orchestrateur, monkeypatch):
    requetes = []

    async def capter(q, categorie="manuel"):
        requetes.append(q)
        return []

    monkeypatch.setattr(orchestrateur.tavily_service, "search", capter)
    run(orchestrateur.analyser_opportunites("formation en intelligence artificielle"))
    assert "Madagascar" in requetes[0]


# ---- analyser_opportunites — tous les lots échouent (fallback) ----

def test_analyser_opportunites_tous_lots_echouent_fallback(orchestrateur, monkeypatch):
    monkeypatch.setattr(orchestrateur.tavily_service, "search", _async(lambda q, **kw: [_opportunite_brute()]))
    monkeypatch.setattr(vo_module, "rank_results", lambda results, query: results)
    monkeypatch.setattr(orchestrateur.llm_service, "analyze", _async(lambda *a, **k: None))

    resultat = run(orchestrateur.analyser_opportunites("formation IA"))

    assert resultat["status"] == "technical_error"
    assert resultat["ai_provider"] == "fallback"
    assert resultat["opportunities"] == []


def test_analyser_opportunites_lots_tentes_zero_opportunite(orchestrateur, monkeypatch):
    monkeypatch.setattr(orchestrateur.tavily_service, "search", _async(lambda q, **kw: [_opportunite_brute()]))
    monkeypatch.setattr(vo_module, "rank_results", lambda results, query: results)
    monkeypatch.setattr(
        orchestrateur.llm_service, "analyze",
        _async(lambda *a, **k: {"opportunities": [], "market_signals": [], "notes": "Rien de pertinent."}),
    )

    resultat = run(orchestrateur.analyser_opportunites("formation IA"))

    assert resultat["status"] == "no_results"
    assert resultat["total"] == 0
    assert resultat["statistics"]["groq_results"] == 0


def test_echec_un_lot_ne_devient_pas_no_results(orchestrateur, monkeypatch):
    monkeypatch.setattr(vo_module, "VEILLE_PAUSE_LLM_S", 0)
    monkeypatch.setattr(vo_module, "MAX_RESULTS_AI", 1)
    monkeypatch.setattr(vo_module, "MAX_FALLBACK_BATCHES", 2)
    monkeypatch.setattr(vo_module, "rank_results", lambda results, query: results)
    monkeypatch.setattr(orchestrateur.tavily_service, "search",
                        _async(lambda *a, **k: [_opportunite_brute("A"), _opportunite_brute("B")]))
    reponses = iter([None, {"opportunities": []}])
    monkeypatch.setattr(orchestrateur.llm_service, "analyze", _async(lambda *a, **k: next(reponses)))
    result = run(orchestrateur.analyser_opportunites("formation", sync_backend=False))
    assert result["status"] == "partial"
    assert result["statistics"]["sources_analyzed"] == 1
    assert result["statistics"]["failed_batches"] == 1


def test_quota_arrete_les_requetes_suivantes(orchestrateur, monkeypatch):
    appels = []
    async def quota(query, **kwargs):
        appels.append(query)
        return {"opportunities": [], "status": "quota_atteint"}
    monkeypatch.setattr(orchestrateur, "analyser_opportunites", quota)
    result = run(orchestrateur.detecter_automatiquement(["q1", "q2", "q3"], sync_backend=False))
    assert appels == ["q1"]
    assert result["status"] == "quota_atteint"
    assert result["queries"][1]["skipped"] is True


def test_rejets_et_sources_restantes_consultables(orchestrateur, monkeypatch):
    monkeypatch.setattr(vo_module, "MAX_RESULTS_AI", 1)
    monkeypatch.setattr(vo_module, "MAX_FALLBACK_BATCHES", 1)
    sources = [{"title": t, "url": f"https://{t}.mg/avis", "content": "Formation informatique"}
               for t in ("alpha", "beta")]
    monkeypatch.setattr(orchestrateur.tavily_service, "search", _async(lambda *a, **k: sources))
    monkeypatch.setattr(vo_module, "rank_results", lambda results, query: results)
    monkeypatch.setattr(orchestrateur.llm_service, "analyze", _async(lambda *a, **k: {
        "opportunities": [], "rejets": [{"resultat": 1, "raison": "Date limite dépassée"}],
        "sources_submitted": 1,
    }))
    result = run(orchestrateur.analyser_opportunites("formation", sync_backend=False))
    assert result["status"] == "partial"
    assert result["opportunities"] == []
    analyzed = result["analyzed_sources"]
    assert analyzed[0]["url"] == sources[0]["url"]
    assert analyzed[0]["analysis_status"] == "rejected"
    assert analyzed[0]["reason"] == "Date limite dépassée"
    assert analyzed[0]["reason_origin"] == "groq"
    assert result["pending_sources"][0]["title"] == "beta"
    assert result["pending_sources"][0]["reason"] is None


def test_absence_raison_et_sources_hors_prompt_ne_sont_pas_rejetees(orchestrateur, monkeypatch):
    monkeypatch.setattr(vo_module, "MAX_RESULTS_AI", 2)
    monkeypatch.setattr(vo_module, "MAX_FALLBACK_BATCHES", 1)
    sources = [{"title": t, "url": f"https://{t}.mg/avis"} for t in ("alpha", "beta")]
    monkeypatch.setattr(orchestrateur.tavily_service, "search", _async(lambda *a, **k: sources))
    monkeypatch.setattr(vo_module, "rank_results", lambda results, query: results)
    monkeypatch.setattr(orchestrateur.llm_service, "analyze", _async(lambda *a, **k: {
        "opportunities": [], "rejets": [{"resultat": 2, "raison": "invention"}],
        "sources_submitted": 1,
    }))
    result = run(orchestrateur.analyser_opportunites("formation", sync_backend=False))
    assert result["analyzed_sources"][0]["analysis_status"] == "undecided"
    assert result["pending_sources"][0]["analysis_status"] == "pending"
    assert result["statistics"]["sources_analyzed"] == 1
    assert result["statistics"]["sources_unanalyzed"] == 1


def test_diagnostic_echec_reste_a_verifier(orchestrateur, monkeypatch):
    monkeypatch.setattr(vo_module, "MAX_FALLBACK_BATCHES", 1)
    monkeypatch.setattr(orchestrateur.tavily_service, "search", _async(lambda *a, **k: [_opportunite_brute()]))
    result = run(orchestrateur.analyser_opportunites("formation", sync_backend=False))
    assert result["status"] == "technical_error"
    assert result["analyzed_sources"] == []
    assert result["pending_sources"][0]["analysis_status"] == "failed"


def test_source_proposee_mais_expiree_explique_le_zero(orchestrateur, monkeypatch):
    source = _opportunite_brute()
    monkeypatch.setattr(orchestrateur.tavily_service, "search", _async(lambda *a, **k: [source]))
    monkeypatch.setattr(orchestrateur.llm_service, "analyze", _async(lambda *a, **k: {
        "opportunities": [{"title": "Formation IA Madagascar", "url": source["url"],
                           "deadline": "2020-01-01"}],
    }))
    monkeypatch.setattr(vo_module.validation_service, "normalize_opportunity", lambda o: o)
    monkeypatch.setattr(vo_module.validation_service, "quality_filter", lambda o: True)
    result = run(orchestrateur.analyser_opportunites("formation", sync_backend=False))
    assert result["opportunities"] == []
    record = result["analyzed_sources"][0]
    assert record["analysis_status"] == "proposed"
    assert record["final_status"] == "rejected"
    assert "2020-01-01" in record["final_reason"]


def test_candidat_expire_ne_bloque_pas_le_lot_suivant(orchestrateur, monkeypatch):
    monkeypatch.setattr(vo_module, "MAX_RESULTS_AI", 1)
    monkeypatch.setattr(vo_module, "MAX_FALLBACK_BATCHES", 2)
    monkeypatch.setattr(vo_module, "VEILLE_PAUSE_LLM_S", 0)
    sources = [{"title": t, "url": f"https://{t}.mg/avis"} for t in ("alpha", "beta")]
    monkeypatch.setattr(orchestrateur.tavily_service, "search", _async(lambda *a, **k: sources))
    monkeypatch.setattr(vo_module, "rank_results", lambda results, query: results)
    responses = iter([
        {"opportunities": [{"title": "Ancienne formation Madagascar", "url": sources[0]["url"],
                            "deadline": "2020-01-01"}]},
        {"opportunities": [{"title": "Formation IA Madagascar", "url": sources[1]["url"]}]},
    ])
    monkeypatch.setattr(orchestrateur.llm_service, "analyze", _async(lambda *a, **k: next(responses)))
    monkeypatch.setattr(vo_module.validation_service, "normalize_opportunity", lambda o: o.copy())
    monkeypatch.setattr(vo_module.validation_service, "quality_filter", lambda o: True)
    monkeypatch.setattr(vo_module.validation_service, "validate_against_schema", lambda o: o)
    result = run(orchestrateur.analyser_opportunites("formation", sync_backend=False))
    assert result["total"] == 1
    assert result["opportunities"][0]["url"] == sources[1]["url"]
    assert result["statistics"]["sources_analyzed"] == 2
    assert result["pending_sources"] == []
    assert [r["final_status"] for r in result["analyzed_sources"]] == ["rejected", "retained"]


# ---- analyser_opportunites — pipeline complet (succès) ----

def test_analyser_opportunites_success_complet(orchestrateur, monkeypatch):
    monkeypatch.setattr(orchestrateur.tavily_service, "search", _async(lambda q, **kw: [_opportunite_brute()]))
    monkeypatch.setattr(vo_module, "rank_results", lambda results, query: results)
    monkeypatch.setattr(
        orchestrateur.llm_service, "analyze",
        _async(lambda *a, **k: {
            "opportunities": [{"title": "Formation IA", "url": "https://x.mg", "organizer": "ONG X"}],
            "market_signals": ["Demande croissante en IA"],
            "notes": "1 opportunité pertinente détectée.",
        }),
    )
    monkeypatch.setattr(vo_module.validation_service, "normalize_opportunity", lambda o: {**o, "score": 0, "confidence": 0})
    monkeypatch.setattr(vo_module.validation_service, "quality_filter", lambda o: True)
    monkeypatch.setattr(vo_module.validation_service, "validate_against_schema", lambda o: o)

    resultat = run(orchestrateur.analyser_opportunites("formation IA"))

    assert resultat["status"] == "success"
    assert resultat["total"] == 1
    assert resultat["opportunities"][0]["status"] == "validated"
    assert resultat["opportunities"][0]["country_scope"] == "Madagascar"
    # HITL : le sync est différé jusqu'à approbation humaine
    assert resultat["statistics"]["backend_sync"]["deferred"] is True
    assert resultat["_review_id"] == "review-test-001"
    assert resultat["_review_status"] == "pending_review"


def test_analyser_opportunites_rejets_normalize_et_quality_et_score_bas(orchestrateur, monkeypatch):
    monkeypatch.setattr(orchestrateur.tavily_service, "search", _async(lambda q, **kw: [_opportunite_brute()]))
    monkeypatch.setattr(vo_module, "rank_results", lambda results, query: results)
    monkeypatch.setattr(
        orchestrateur.llm_service, "analyze",
        _async(lambda *a, **k: {
            "opportunities": [
                {"title": "Rejetée par normalize", "url": "https://a.mg"},
                {"title": "Rejetée par quality_filter", "url": "https://b.mg"},
                {"title": "Rejetée par score trop bas", "url": "https://c.mg"},
            ],
            "market_signals": [], "notes": "x",
        }),
    )

    appels = {"normalize": 0}

    def faux_normalize(o):
        appels["normalize"] += 1
        if appels["normalize"] == 1:
            return None  # rejetée
        return {**o, "score": 0, "confidence": 0}

    monkeypatch.setattr(vo_module.validation_service, "normalize_opportunity", faux_normalize)
    monkeypatch.setattr(
        vo_module.validation_service, "quality_filter",
        lambda o: "quality_filter" not in o.get("title", ""),
    )
    monkeypatch.setattr(orchestrateur.scoring_service, "score", lambda c, **kw: {"score": 1, "confidence": 0.9})  # < MIN_SCORE_TO_REVIEW

    resultat = run(orchestrateur.analyser_opportunites("formation IA"))

    stats = resultat["statistics"]
    assert stats["rejected_normalize"] == 1
    assert stats["rejected_quality_filter"] == 1
    assert stats["rejected_score_bas"] == 1
    assert resultat["total"] == 0


def test_finalisation_compte_echeance_et_zone_rejetees(orchestrateur, monkeypatch):
    monkeypatch.setattr(vo_module.validation_service, "normalize_opportunity", lambda o: o)
    monkeypatch.setattr(vo_module.validation_service, "quality_filter", lambda o: True)
    resultat = run(orchestrateur._finalize_opportunities(
        groq_opportunities=[
            {"title": "Expirée Madagascar", "deadline": "2020-01-01"},
            {"title": "Hors zone", "summary": "Paris", "url": "https://example.fr"},
        ],
        groq_response={}, start_total=0.0, sync_backend=False,
    ))
    assert resultat["status"] == "no_results"
    assert resultat["statistics"]["rejected_deadline_expired"] == 1
    assert resultat["statistics"]["rejected_outside_madagascar"] == 1


def test_analyser_opportunites_sync_backend_desactivee(orchestrateur, monkeypatch):
    monkeypatch.setattr(orchestrateur.tavily_service, "search", _async(lambda q, **kw: [_opportunite_brute()]))
    monkeypatch.setattr(vo_module, "rank_results", lambda results, query: results)
    monkeypatch.setattr(
        orchestrateur.llm_service, "analyze",
        _async(lambda *a, **k: {"opportunities": [{"title": "x"}], "market_signals": [], "notes": "x"}),
    )
    monkeypatch.setattr(vo_module.validation_service, "normalize_opportunity", lambda o: {**o, "score": 0, "confidence": 0})
    monkeypatch.setattr(vo_module.validation_service, "quality_filter", lambda o: True)
    monkeypatch.setattr(vo_module.validation_service, "validate_against_schema", lambda o: o)

    resultat = run(orchestrateur.analyser_opportunites("formation IA", sync_backend=False))

    assert resultat["statistics"]["backend_sync"]["deferred"] is True


# ---- detecter_automatiquement ----

def test_detecter_automatiquement_aucune_requete(orchestrateur):
    resultat = run(orchestrateur.detecter_automatiquement([]))
    assert resultat["status"] == "error"


def test_detecter_automatiquement_success(orchestrateur, monkeypatch):
    async def faux_analyser(query, sync_backend=False, categorie="auto"):
        return {
            "status": "success",
            "opportunities": [{"title": f"Opp de {query}", "score": 50, "url": f"https://{query}.mg"}],
        }

    monkeypatch.setattr(orchestrateur, "analyser_opportunites", faux_analyser)

    resultat = run(orchestrateur.detecter_automatiquement(["formation IA", "formation data"], min_score=40, limit=10))

    assert resultat["mode"] == "automatique"
    assert resultat["status"] == "success"
    assert resultat["total"] == 2
    assert resultat["statistics"]["backend_sync"]["sent"] == 2


def test_detecter_automatiquement_distingue_zero_resultat_et_succes(orchestrateur, monkeypatch):
    async def faux_analyser(*args, **kwargs):
        return {"status": "no_results", "opportunities": []}

    monkeypatch.setattr(orchestrateur, "analyser_opportunites", faux_analyser)
    resultat = run(orchestrateur.detecter_automatiquement(["formation IA"]))
    assert resultat["status"] == "no_results"
    assert resultat["total"] == 0


def test_detecter_automatiquement_requete_en_echec_statut_degrade(orchestrateur, monkeypatch):
    async def faux_analyser(query, sync_backend=False, categorie="auto"):
        raise RuntimeError("Tavily indisponible")

    monkeypatch.setattr(orchestrateur, "analyser_opportunites", faux_analyser)

    resultat = run(orchestrateur.detecter_automatiquement(["formation IA"]))

    assert resultat["status"] == "technical_error"
    assert resultat["queries"][0]["status"] == "error"


def test_detecter_automatiquement_statut_partiel(orchestrateur, monkeypatch):
    appels = {"n": 0}

    async def faux_analyser(query, sync_backend=False, categorie="auto"):
        appels["n"] += 1
        if appels["n"] == 1:
            raise RuntimeError("échec")
        return {"status": "success", "opportunities": [{"title": "x", "score": 50, "url": "https://x.mg"}]}

    monkeypatch.setattr(orchestrateur, "analyser_opportunites", faux_analyser)

    resultat = run(orchestrateur.detecter_automatiquement(["q1", "q2"]))

    assert resultat["status"] == "partial"


def test_detecter_automatiquement_filtre_min_score_et_limit(orchestrateur, monkeypatch):
    async def faux_analyser(query, sync_backend=False, categorie="auto"):
        return {
            "status": "success",
            "opportunities": [
                {"title": "Haute", "score": 90, "url": "https://a.mg"},
                {"title": "Basse", "score": 10, "url": "https://b.mg"},
            ],
        }

    monkeypatch.setattr(orchestrateur, "analyser_opportunites", faux_analyser)

    resultat = run(orchestrateur.detecter_automatiquement(["q1"], min_score=40, limit=1))

    assert resultat["total"] == 1
    assert resultat["opportunities"][0]["title"] == "Haute"


# ---- analyser_texte ----

def test_analyser_texte_vide(orchestrateur):
    resultat = run(orchestrateur.analyser_texte(""))
    assert resultat["status"] == "error"


def test_analyser_texte_llm_echoue_fallback(orchestrateur, monkeypatch):
    monkeypatch.setattr(orchestrateur.llm_service, "analyze", _async(lambda *a, **k: None))
    resultat = run(orchestrateur.analyser_texte("Appel d'offre pour une formation en IA."))
    assert resultat["status"] == "technical_error"
    assert resultat["ai_provider"] == "fallback"


def test_analyser_texte_success(orchestrateur, monkeypatch):
    monkeypatch.setattr(
        orchestrateur.llm_service, "analyze",
        _async(lambda *a, **k: {"opportunities": [{"title": "x"}], "market_signals": [], "notes": "x"}),
    )
    monkeypatch.setattr(vo_module.validation_service, "normalize_opportunity", lambda o: {**o, "score": 0, "confidence": 0})
    monkeypatch.setattr(vo_module.validation_service, "quality_filter", lambda o: True)
    monkeypatch.setattr(vo_module.validation_service, "validate_against_schema", lambda o: o)

    resultat = run(orchestrateur.analyser_texte("Appel d'offre pour une formation en IA.", source="collage"))

    assert resultat["status"] == "no_results"
    assert resultat["statistics"]["text_length_chars"] > 0


def test_split_texte_en_sources_texte_court():
    chunks = VeilleOrchestrator._split_texte_en_sources("Texte court.", "manuel")
    assert len(chunks) == 1
    assert chunks[0]["content"] == "Texte court."


# ---- analyser_pdf — corrigé le 2026-09-24 (_extract_pdf_text, PyPDF2) ----

def test_analyser_pdf_pdf_vide(orchestrateur):
    resultat = run(orchestrateur.analyser_pdf(b"", filename="vide.pdf"))
    assert resultat["status"] == "error"
    assert resultat["notes"] == "PDF vide."


def test_analyser_pdf_invalide_ou_corrompu(orchestrateur):
    resultat = run(orchestrateur.analyser_pdf(b"ceci n'est pas un PDF", filename="corrompu.pdf"))
    assert resultat["status"] == "error"
    assert "Erreur extraction PDF" in resultat["notes"]


def test_analyser_pdf_aucun_texte_extrait(orchestrateur, monkeypatch):
    monkeypatch.setattr(VeilleOrchestrator, "_extract_pdf_text", staticmethod(lambda pdf_bytes: "   "))
    resultat = run(orchestrateur.analyser_pdf(b"%PDF-1.4 ...", filename="scan_image.pdf"))
    assert resultat["status"] == "no_results"
    assert resultat["notes"] == "Aucun texte extrait du PDF."


def test_analyser_pdf_success_reutilise_analyser_texte(orchestrateur, monkeypatch):
    monkeypatch.setattr(
        VeilleOrchestrator, "_extract_pdf_text",
        staticmethod(lambda pdf_bytes: "Appel d'offre pour une formation en IA."),
    )
    monkeypatch.setattr(
        orchestrateur.llm_service, "analyze",
        _async(lambda *a, **k: {"opportunities": [{"title": "x"}], "market_signals": [], "notes": "x"}),
    )
    monkeypatch.setattr(vo_module.validation_service, "normalize_opportunity", lambda o: {**o, "score": 0, "confidence": 0})
    monkeypatch.setattr(vo_module.validation_service, "quality_filter", lambda o: True)
    monkeypatch.setattr(vo_module.validation_service, "validate_against_schema", lambda o: o)

    resultat = run(orchestrateur.analyser_pdf(b"%PDF-1.4 ...", filename="ao.pdf"))

    assert resultat["status"] == "no_results"
    assert resultat["statistics"]["pdf_filename"] == "ao.pdf"
    assert resultat["statistics"]["pdf_size_bytes"] > 0


# ---- Helpers directs ----

def test_empty_response_structure():
    resultat = VeilleOrchestrator._empty_response(status="error", notes="Test.")
    assert resultat["opportunities"] == []
    assert resultat["statistics"]["raw_results"] == 0


def test_rechercher_alias_appelle_analyser_opportunites(orchestrateur, monkeypatch):
    appels = []

    async def faux_analyser(query, sync_backend=True, categorie="auto"):
        appels.append(query)
        return {"status": "success"}

    monkeypatch.setattr(orchestrateur, "analyser_opportunites", faux_analyser)
    run(orchestrateur.rechercher("formation IA"))
    assert appels == ["formation IA"]
