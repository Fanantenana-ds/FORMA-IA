# tests/unit/test_benchmark_runner.py
# ============================================================
# Correction 1c — Mission "Étape 1"
# ============================================================
# Le benchmark M1 (BenchmarkRunner.run) rejoue le corpus annoté à travers
# VeilleOrchestrator.analyser_texte(), qui SYNCHRONISAIT chaque
# "opportunité" détectée avec le Backend réel (POST /opportunites) —
# lancer le benchmark polluait la base formaia avec des données de test.
# analyser_texte() n'avait aucun moyen de désactiver cette synchronisation
# (contrairement à analyser_opportunites(), qui a déjà sync_backend).
#
# Aucun réseau réel : LLM et sync Backend doublés au niveau de
# l'orchestrateur réel construit par BenchmarkRunner (même pattern que
# tests/unit/test_veille_orchestrator.py).
# ============================================================

import asyncio
import json

import pytest

from app.orchestrator import veille_orchestrator as vo_module
from app.services.benchmark.benchmark_runner import BenchmarkRunner


def run(coro):
    return asyncio.run(coro)


def _async(fn):
    async def wrapper(*args, **kwargs):
        return fn(*args, **kwargs)
    return wrapper


LIGNE_CORPUS = {
    "id": "corpus-test-0001",
    "raw_text": "ALTIORA recrute un formateur en IA à Antananarivo, budget 5M Ar, échéance 15 septembre 2026.",
    "gold": {
        "is_opportunity": True, "domain": "ia",
        "budget_expected": "5M Ar", "deadline_expected": "2026-09-15",
    },
}


@pytest.fixture
def corpus_test(tmp_path):
    chemin = tmp_path / "corpus_test.jsonl"
    chemin.write_text(json.dumps(LIGNE_CORPUS, ensure_ascii=False), encoding="utf-8")
    return chemin


@pytest.fixture
def appels_sync_backend(monkeypatch):
    """Espionne sync_opportunities_to_backend : doit rester VIDE pendant
    tout le benchmark (correction 1c)."""
    appels = []

    async def espion(opportunites):
        appels.append(opportunites)
        return {"enabled": True, "sent": len(opportunites), "failed": 0}

    monkeypatch.setattr(vo_module, "sync_opportunities_to_backend", espion)
    return appels


@pytest.fixture
def runner(corpus_test, monkeypatch, appels_sync_backend):
    r = BenchmarkRunner(corpus_path=corpus_test)

    async def faux_analyze(query, results):
        return {"opportunities": [{
            "title": "Formation IA", "summary": "Recrutement formateur IA",
            "domain": "ia", "budget": "5M Ar", "deadline": "2026-09-15",
            "organizer": "ALTIORA", "url": "https://example.mg/ao",
            "confidence": 0.9, "opportunity_type": "formation",
        }]}

    monkeypatch.setattr(r.orchestrator.llm_service, "analyze", faux_analyze)
    return r


def test_benchmark_ne_synchronise_jamais_avec_le_backend(runner, appels_sync_backend):
    resultat = run(runner.run(limit=1))

    assert resultat["corpus_size_tested"] == 1
    assert appels_sync_backend == []  # AUCUN appel Backend pendant le benchmark


def test_benchmark_calcule_quand_meme_les_indicateurs(runner):
    """La désactivation de la sync ne doit pas casser le calcul des métriques."""
    resultat = run(runner.run(limit=1))

    assert resultat["confusion_matrix"]["true_positives"] == 1
    assert resultat["precision_detection"] == 1.0
