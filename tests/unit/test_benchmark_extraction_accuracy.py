# tests/unit/test_benchmark_extraction_accuracy.py
# ============================================================
# Correction 1d — Mission "Étape 1"
# ============================================================
# AVANT cette correction, extraction_accuracy comptait un champ (budget,
# deadline) comme "correct" dès qu'il était NON VIDE — sans jamais le
# comparer à la valeur attendue (gold). Un budget totalement faux
# ("50M Ar" prédit alors que le gold attend "5M Ar") était donc compté
# comme une extraction réussie. Le chiffre "> 90 %" du CDC était donc
# invérifiable, potentiellement faux. De plus, l'organisateur n'était pas
# comparé du tout, et aucune valeur "inventée" par le LLM (un champ
# rempli alors que le gold n'attend rien) n'était détectée.
#
# Aucun réseau réel.
# ============================================================

import asyncio
import json

import pytest

from app.orchestrator import veille_orchestrator as vo_module
from app.services.benchmark.benchmark_runner import (
    BenchmarkRunner,
    _valeur_correcte,
    _est_valeur_inventee,
)


def run(coro):
    return asyncio.run(coro)


# ============================================================
# Fonctions pures de comparaison
# ============================================================

def test_valeur_correcte_match_exact():
    assert _valeur_correcte("ALTIORA", "ALTIORA") is True


def test_valeur_correcte_insensible_casse_et_espaces():
    assert _valeur_correcte("  altiora  ", "ALTIORA") is True


def test_valeur_correcte_budget_faux_n_est_plus_compte_correct():
    """LE bug corrigé : une valeur non vide mais DIFFÉRENTE du gold doit
    être refusée, pas acceptée juste parce qu'elle est non vide."""
    assert _valeur_correcte("50M Ar", "5M Ar") is False


def test_valeur_correcte_vide_est_incorrecte():
    assert _valeur_correcte(None, "5M Ar") is False
    assert _valeur_correcte("Non précisé", "5M Ar") is False
    assert _valeur_correcte("", "5M Ar") is False


def test_valeur_correcte_dates_identiques_format_iso():
    assert _valeur_correcte("2026-09-15", "2026-09-15", est_date=True) is True


def test_valeur_correcte_dates_differentes_meme_format():
    assert _valeur_correcte("2026-09-16", "2026-09-15", est_date=True) is False


def test_valeur_correcte_pas_de_similarite_floue_pour_un_chiffre_different():
    """Une comparaison floue masquerait ce genre d'erreur -- volontairement
    exclue (voir commentaire dans _valeur_correcte)."""
    assert _valeur_correcte("5M Ar", "50M Ar") is False


def test_est_valeur_inventee_true_si_non_vide():
    assert _est_valeur_inventee("Un organisateur inventé") is True


def test_est_valeur_inventee_false_si_vide():
    assert _est_valeur_inventee(None) is False
    assert _est_valeur_inventee("") is False
    assert _est_valeur_inventee("Non précisé") is False


# ============================================================
# Intégration — BenchmarkRunner.run()
# ============================================================

def _async(fn):
    async def wrapper(*args, **kwargs):
        return fn(*args, **kwargs)
    return wrapper


@pytest.fixture(autouse=True)
def pas_de_sync_backend(monkeypatch):
    monkeypatch.setattr(
        vo_module, "sync_opportunities_to_backend",
        _async(lambda opps: {"enabled": True, "sent": len(opps), "failed": 0}),
    )


def _corpus(tmp_path, gold_extra):
    ligne = {
        "id": "corpus-test-0001",
        "raw_text": "ALTIORA recrute un formateur en IA, budget 5M Ar, échéance 15 septembre 2026.",
        "gold": {"is_opportunity": True, "domain": "ia", **gold_extra},
    }
    chemin = tmp_path / "corpus.jsonl"
    chemin.write_text(json.dumps(ligne, ensure_ascii=False), encoding="utf-8")
    return chemin


def _runner_avec_prediction(tmp_path, monkeypatch, gold_extra, prediction_extra):
    chemin = _corpus(tmp_path, gold_extra)
    r = BenchmarkRunner(corpus_path=chemin)

    async def faux_analyze(query, results):
        return {"opportunities": [{
            "title": "Formation IA", "summary": "Recrutement formateur IA",
            "domain": "ia", "confidence": 0.9, "opportunity_type": "autre",
            **prediction_extra,
        }]}

    monkeypatch.setattr(r.orchestrator.llm_service, "analyze", faux_analyze)
    return r


def test_budget_faux_fait_baisser_extraction_accuracy(tmp_path, monkeypatch):
    """AVANT la correction, ce test aurait donné extraction_accuracy=1.0
    (budget non vide -> compté correct), alors que la valeur est fausse."""
    r = _runner_avec_prediction(
        tmp_path, monkeypatch,
        gold_extra={"budget_expected": "5M Ar"},
        prediction_extra={"budget": "50M Ar", "organizer": None, "deadline": None},
    )

    resultat = run(r.run(limit=1))

    assert resultat["extraction_accuracy"] == 0.0


def test_organisateur_correct_est_compte(tmp_path, monkeypatch):
    """L'organisateur n'était pas comparé du tout avant la correction."""
    r = _runner_avec_prediction(
        tmp_path, monkeypatch,
        gold_extra={"organizer_expected": "ALTIORA"},
        prediction_extra={"organizer": "ALTIORA", "budget": None, "deadline": None},
    )

    resultat = run(r.run(limit=1))

    assert resultat["extraction_accuracy"] == 1.0


def test_valeur_inventee_par_le_llm_est_signalee(tmp_path, monkeypatch):
    """Le gold n'attend AUCUN budget (champ absent) mais le LLM en
    invente un quand même -> doit être signalé, pas compté comme réussite."""
    r = _runner_avec_prediction(
        tmp_path, monkeypatch,
        gold_extra={},  # aucun champ *_expected
        prediction_extra={"budget": "12M Ar", "organizer": None, "deadline": None},
    )

    resultat = run(r.run(limit=1))

    assert resultat["hallucinated_values"]["budget"] == 1
    assert resultat["hallucinated_values"]["total"] == 1
    assert resultat["extraction_accuracy"] is None  # rien n'était attendu, rien à mesurer
