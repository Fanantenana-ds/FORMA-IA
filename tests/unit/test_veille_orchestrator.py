# ============================================================
# TESTS — app/orchestrator/veille_orchestrator.py (M1)
# ============================================================
# Aucun appel réseau réel (Tavily/Groq/Backend) : tout est doublé au niveau
# des services déjà instanciés par l'orchestrateur, comme pour les autres
# orchestrateurs de la suite (tdr_orchestrator, facturation_orchestrator).
# ============================================================

import asyncio

import pytest

from app.orchestrator import veille_orchestrator as vo_module
from app.orchestrator.veille_orchestrator import VeilleOrchestrator


def run(coro):
    return asyncio.run(coro)


@pytest.fixture
def orchestrateur(monkeypatch):
    o = VeilleOrchestrator()
    # Doublures par défaut : "aucun résultat" (chaque test les redéfinit au besoin)
    monkeypatch.setattr(o.tavily_service, "search", _async(lambda q: []))
    monkeypatch.setattr(o.llm_service, "analyze", _async(lambda *a, **k: None))
    monkeypatch.setattr(o.classification_service, "classify", lambda c: {"domain": "ia"})
    monkeypatch.setattr(o.classification_service, "detect_country", lambda c: "Madagascar")
    monkeypatch.setattr(o.scoring_service, "score", lambda c: {"score": 80, "confidence": 0.9})
    monkeypatch.setattr(
        vo_module, "sync_opportunities_to_backend",
        _async(lambda opps: {"enabled": True, "sent": len(opps), "failed": 0}),
    )
    monkeypatch.setattr(
        vo_module, "sync_new_opportunities_to_backend",
        _async(lambda opps: {"enabled": True, "sent": len(opps), "failed": 0, "already_present": 0}),
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
    monkeypatch.setattr(orchestrateur.tavily_service, "search", _async(lambda q: []))
    resultat = run(orchestrateur.analyser_opportunites("formation IA"))
    assert resultat["status"] == "no_results"


def test_analyser_opportunites_aucun_resultat_apres_prefiltre(orchestrateur, monkeypatch):
    monkeypatch.setattr(orchestrateur.tavily_service, "search", _async(lambda q: [_opportunite_brute()]))
    monkeypatch.setattr(vo_module, "rank_results", lambda results, query: [])
    resultat = run(orchestrateur.analyser_opportunites("formation IA"))
    assert resultat["status"] == "no_results"
    assert resultat["statistics"]["raw_results"] == 1


def test_analyser_opportunites_ajoute_contexte_madagascar(orchestrateur, monkeypatch):
    requetes = []

    async def capter(q):
        requetes.append(q)
        return []

    monkeypatch.setattr(orchestrateur.tavily_service, "search", capter)
    run(orchestrateur.analyser_opportunites("formation en intelligence artificielle"))
    assert "Madagascar" in requetes[0]


# ---- analyser_opportunites — tous les lots échouent (fallback) ----

def test_analyser_opportunites_tous_lots_echouent_fallback(orchestrateur, monkeypatch):
    monkeypatch.setattr(orchestrateur.tavily_service, "search", _async(lambda q: [_opportunite_brute()]))
    monkeypatch.setattr(vo_module, "rank_results", lambda results, query: results)
    monkeypatch.setattr(orchestrateur.llm_service, "analyze", _async(lambda *a, **k: None))

    resultat = run(orchestrateur.analyser_opportunites("formation IA"))

    assert resultat["status"] == "degraded"
    assert resultat["ai_provider"] == "fallback"
    assert resultat["opportunities"] == []


def test_analyser_opportunites_lots_tentes_zero_opportunite(orchestrateur, monkeypatch):
    monkeypatch.setattr(orchestrateur.tavily_service, "search", _async(lambda q: [_opportunite_brute()]))
    monkeypatch.setattr(vo_module, "rank_results", lambda results, query: results)
    monkeypatch.setattr(
        orchestrateur.llm_service, "analyze",
        _async(lambda *a, **k: {"opportunities": [], "market_signals": [], "notes": "Rien de pertinent."}),
    )

    resultat = run(orchestrateur.analyser_opportunites("formation IA"))

    assert resultat["status"] == "success"
    assert resultat["total"] == 0
    assert resultat["statistics"]["groq_results"] == 0


# ---- analyser_opportunites — pipeline complet (succès) ----

def test_analyser_opportunites_success_complet(orchestrateur, monkeypatch):
    monkeypatch.setattr(orchestrateur.tavily_service, "search", _async(lambda q: [_opportunite_brute()]))
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
    assert resultat["statistics"]["backend_sync"]["sent"] == 1


def test_analyser_opportunites_rejets_normalize_et_quality_et_score_bas(orchestrateur, monkeypatch):
    monkeypatch.setattr(orchestrateur.tavily_service, "search", _async(lambda q: [_opportunite_brute()]))
    monkeypatch.setattr(vo_module, "rank_results", lambda results, query: results)
    monkeypatch.setattr(
        orchestrateur.llm_service, "analyze",
        _async(lambda *a, **k: {
            "opportunities": [
                {"title": "Rejetée par normalize"},
                {"title": "Rejetée par quality_filter"},
                {"title": "Rejetée par score trop bas"},
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
    monkeypatch.setattr(orchestrateur.scoring_service, "score", lambda c: {"score": 1, "confidence": 0.9})  # < MIN_SCORE_TO_REVIEW

    resultat = run(orchestrateur.analyser_opportunites("formation IA"))

    stats = resultat["statistics"]
    assert stats["rejected_normalize"] == 1
    assert stats["rejected_quality_filter"] == 1
    assert stats["rejected_score_bas"] == 1
    assert resultat["total"] == 0


def test_analyser_opportunites_sync_backend_desactivee(orchestrateur, monkeypatch):
    monkeypatch.setattr(orchestrateur.tavily_service, "search", _async(lambda q: [_opportunite_brute()]))
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
    async def faux_analyser(query, sync_backend=False):
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


def test_detecter_automatiquement_requete_en_echec_statut_degrade(orchestrateur, monkeypatch):
    async def faux_analyser(query, sync_backend=False):
        raise RuntimeError("Tavily indisponible")

    monkeypatch.setattr(orchestrateur, "analyser_opportunites", faux_analyser)

    resultat = run(orchestrateur.detecter_automatiquement(["formation IA"]))

    assert resultat["status"] == "degraded"
    assert resultat["queries"][0]["status"] == "error"


def test_detecter_automatiquement_statut_partiel(orchestrateur, monkeypatch):
    appels = {"n": 0}

    async def faux_analyser(query, sync_backend=False):
        appels["n"] += 1
        if appels["n"] == 1:
            raise RuntimeError("échec")
        return {"status": "success", "opportunities": [{"title": "x", "score": 50, "url": "https://x.mg"}]}

    monkeypatch.setattr(orchestrateur, "analyser_opportunites", faux_analyser)

    resultat = run(orchestrateur.detecter_automatiquement(["q1", "q2"]))

    assert resultat["status"] == "partial"


def test_detecter_automatiquement_filtre_min_score_et_limit(orchestrateur, monkeypatch):
    async def faux_analyser(query, sync_backend=False):
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
    assert resultat["status"] == "degraded"
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

    assert resultat["status"] == "success"
    assert resultat["statistics"]["text_length_chars"] > 0


def test_split_texte_en_sources_texte_court():
    chunks = VeilleOrchestrator._split_texte_en_sources("Texte court.", "manuel")
    assert len(chunks) == 1
    assert chunks[0]["content"] == "Texte court."


# ---- analyser_pdf — bug connu, non corrigé (hors périmètre de cette tâche) ----

@pytest.mark.xfail(strict=True, reason=(
    "self.pdf_extraction_service n'est jamais initialisé dans __init__ "
    "(aucune classe PDFExtractionService dans le projet) : analyser_pdf() "
    "lève AttributeError avant même d'atteindre son propre garde-fou "
    "'if not self.pdf_extraction_service'. Route /ia/veille/... concernée "
    "dans routes_veille.py. Signalé, non corrigé (hors périmètre de la tâche "
    "couverture de tests)."
))
def test_analyser_pdf_service_extraction_jamais_initialise(orchestrateur):
    resultat = run(orchestrateur.analyser_pdf(b"%PDF-1.4 ...", filename="ao.pdf"))
    assert resultat["status"] == "error"


# ---- Helpers directs ----

def test_empty_response_structure():
    resultat = VeilleOrchestrator._empty_response(status="error", notes="Test.")
    assert resultat["opportunities"] == []
    assert resultat["statistics"]["raw_results"] == 0


def test_rechercher_alias_appelle_analyser_opportunites(orchestrateur, monkeypatch):
    appels = []

    async def faux_analyser(query, sync_backend=True):
        appels.append(query)
        return {"status": "success"}

    monkeypatch.setattr(orchestrateur, "analyser_opportunites", faux_analyser)
    run(orchestrateur.rechercher("formation IA"))
    assert appels == ["formation IA"]
