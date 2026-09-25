# tests/unit/test_benchmark_rapport_complet.py
# ============================================================
# Étape C (mission "Préparation soutenance") — rapport complet du benchmark M1
# ============================================================
# Complète 1c/1d (conservés) avec : F1 détection, matrice + F1 macro par
# domaine, extraction PAR CHAMP (pas seulement combinée), latence médiane/p95,
# nombre de replis LLM séparé des erreurs Python réelles (AVANT cette
# correction, une exception dans analyser_texte() faisait planter TOUT le
# benchmark — aucun try/except par document), instantané de configuration,
# et date_reference = date_collected de chaque document (reproductibilité,
# point 1, déjà câblée dans scoring_service.py/veille_orchestrator.py).
#
# Aucun réseau réel : LLM doublé au niveau de l'instance réelle de
# VeilleOrchestrator construite par BenchmarkRunner (même pattern que
# test_benchmark_runner.py). time.perf_counter contrôlé pour des latences
# déterministes (pas de vraie attente).
# ============================================================

import asyncio
import json

import pytest

from app.orchestrator import veille_orchestrator as vo_module
from app.services.benchmark import benchmark_runner as br_module
from app.services.benchmark.benchmark_runner import (
    BenchmarkRunner,
    _f1,
    _percentile,
    _f1_macro_domaine,
    _parser_date_collectee,
)


def run(coro):
    return asyncio.run(coro)


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


# ============================================================
# Fonctions pures
# ============================================================

def test_f1_calcule_correctement():
    assert _f1(1.0, 1.0) == 1.0
    assert _f1(0.5, 0.5) == 0.5
    assert _f1(None, 0.5) is None
    assert _f1(0.0, 0.0) is None  # division par zéro évitée


def test_percentile_mediane_et_p95():
    valeurs = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0]
    assert _percentile(valeurs, 0.5) == pytest.approx(5.5)
    assert _percentile(valeurs, 0.95) == pytest.approx(9.55, abs=0.01)
    assert _percentile([], 0.5) is None


def test_f1_macro_domaine_deux_classes_parfaites():
    matrice = {"ia": {"ia": 2}, "data": {"data": 1}}
    assert _f1_macro_domaine(matrice, ["ia", "data"]) == pytest.approx(1.0)


def test_f1_macro_domaine_avec_confusion():
    # 1 "ia" bien classé, 1 "ia" classé "data" (faux négatif ia, faux positif data)
    matrice = {"ia": {"ia": 1, "data": 1}}
    score = _f1_macro_domaine(matrice, ["ia", "data"])
    assert 0 < score < 1.0


def test_parser_date_collectee_iso_valide():
    d = _parser_date_collectee("2026-09-01")
    assert d is not None and d.year == 2026 and d.month == 9 and d.day == 1


def test_parser_date_collectee_absente_ou_invalide():
    assert _parser_date_collectee(None) is None
    assert _parser_date_collectee("") is None
    assert _parser_date_collectee("pas une date") is None


# ============================================================
# Intégration — BenchmarkRunner.run()
# ============================================================

def _corpus(tmp_path, lignes):
    chemin = tmp_path / "corpus.jsonl"
    chemin.write_text(
        "\n".join(json.dumps(l, ensure_ascii=False) for l in lignes), encoding="utf-8",
    )
    return chemin


def test_erreur_python_sur_un_document_n_interrompt_pas_le_benchmark(tmp_path, monkeypatch):
    """LE bug corrigé : avant, une exception dans analyser_texte() faisait
    planter tout run() (aucun try/except par document)."""
    lignes = [
        {"id": "c1", "raw_text": "Texte assez long pour passer la validation minimale du corpus.",
         "gold": {"is_opportunity": False}},
        {"id": "c2", "raw_text": "Un second texte assez long lui aussi pour la validation du corpus.",
         "gold": {"is_opportunity": False}},
    ]
    chemin = _corpus(tmp_path, lignes)
    runner = BenchmarkRunner(corpus_path=chemin)

    appels = {"n": 0}

    async def analyse_capricieuse(texte, source, sync_backend=True, date_reference=None):
        appels["n"] += 1
        if appels["n"] == 1:
            raise RuntimeError("panne LLM simulée")
        return {"opportunities": [], "ai_provider": "groq"}

    monkeypatch.setattr(runner.orchestrator, "analyser_texte", analyse_capricieuse)

    resultat = run(runner.run(limit=2))

    assert resultat["corpus_size_tested"] == 2
    assert resultat["model_error_count"] == 1
    assert resultat["llm_fallback_count"] == 0


def test_repli_llm_compte_separement_des_erreurs(tmp_path, monkeypatch):
    lignes = [{"id": "c1", "raw_text": "Texte assez long pour passer la validation minimale du corpus.",
               "gold": {"is_opportunity": False}}]
    chemin = _corpus(tmp_path, lignes)
    runner = BenchmarkRunner(corpus_path=chemin)

    async def analyse_repli(texte, source, sync_backend=True, date_reference=None):
        return {"opportunities": [], "ai_provider": "fallback", "status": "degraded"}

    monkeypatch.setattr(runner.orchestrator, "analyser_texte", analyse_repli)

    resultat = run(runner.run(limit=1))

    assert resultat["llm_fallback_count"] == 1
    assert resultat["model_error_count"] == 0


def test_date_reference_transmise_est_bien_date_collected(tmp_path, monkeypatch):
    lignes = [{"id": "c1", "raw_text": "Texte assez long pour passer la validation minimale du corpus.",
               "date_collected": "2026-09-01", "gold": {"is_opportunity": False}}]
    chemin = _corpus(tmp_path, lignes)
    runner = BenchmarkRunner(corpus_path=chemin)

    recu = {}

    async def capter(texte, source, sync_backend=True, date_reference=None):
        recu["date_reference"] = date_reference
        return {"opportunities": []}

    monkeypatch.setattr(runner.orchestrator, "analyser_texte", capter)

    run(runner.run(limit=1))

    assert recu["date_reference"] is not None
    assert recu["date_reference"].isoformat().startswith("2026-09-01")


def test_configuration_snapshot_present(tmp_path, monkeypatch):
    lignes = [{"id": "c1", "raw_text": "Texte assez long pour passer la validation minimale du corpus.",
               "gold": {"is_opportunity": False}}]
    chemin = _corpus(tmp_path, lignes)
    runner = BenchmarkRunner(corpus_path=chemin)
    monkeypatch.setattr(
        runner.orchestrator, "analyser_texte",
        _async(lambda texte, source, sync_backend=True, date_reference=None: {"opportunities": []}),
    )

    resultat = run(runner.run(limit=1))

    snap = resultat["configuration_snapshot"]
    assert "date_execution" in snap
    assert "empreinte_prompts_m1" in snap and len(snap["empreinte_prompts_m1"]) > 0


def test_extraction_par_champ_rapportee_separement(tmp_path, monkeypatch):
    lignes = [{"id": "c1", "raw_text": "Texte assez long pour passer la validation minimale du corpus.",
               "gold": {"is_opportunity": True, "budget_expected": "5M Ar", "organizer_expected": "ALTIORA"}}]
    chemin = _corpus(tmp_path, lignes)
    runner = BenchmarkRunner(corpus_path=chemin)

    async def analyse(texte, source, sync_backend=True, date_reference=None):
        return {"opportunities": [{"budget": "5M Ar", "organizer": "Autre", "domain": "ia"}]}

    monkeypatch.setattr(runner.orchestrator, "analyser_texte", analyse)

    resultat = run(runner.run(limit=1))

    champs = resultat["extraction_par_champ"]
    assert champs["budget"] == {"correct": 1, "total": 1, "accuracy": 1.0}
    assert champs["organizer"] == {"correct": 0, "total": 1, "accuracy": 0.0}
    assert champs["deadline"] == {"correct": 0, "total": 0, "accuracy": None}


def test_f1_detection_et_matrice_domaine_dans_le_rapport(tmp_path, monkeypatch):
    lignes = [
        {"id": "c1", "raw_text": "Texte assez long pour passer la validation minimale du corpus un.",
         "gold": {"is_opportunity": True, "domain": "ia"}},
        {"id": "c2", "raw_text": "Texte assez long pour passer la validation minimale du corpus deux.",
         "gold": {"is_opportunity": True, "domain": "data"}},
    ]
    chemin = _corpus(tmp_path, lignes)
    runner = BenchmarkRunner(corpus_path=chemin)

    async def analyse(texte, source, sync_backend=True, date_reference=None):
        return {"opportunities": [{"domain": "ia"}]}  # toujours "ia", même pour "data"

    monkeypatch.setattr(runner.orchestrator, "analyser_texte", analyse)

    resultat = run(runner.run(limit=2))

    assert resultat["f1_detection"] == 1.0  # détection parfaite (les 2 sont trouvées)
    assert resultat["domain_confusion_matrix"]["data"]["ia"] == 1  # "data" confondu avec "ia"
    assert resultat["f1_macro_domain"] is not None and resultat["f1_macro_domain"] < 1.0


def test_latence_mediane_et_p95_dans_le_rapport(tmp_path, monkeypatch):
    lignes = [
        {"id": f"c{i}", "raw_text": f"Texte numero {i} assez long pour passer la validation minimale du corpus.",
         "gold": {"is_opportunity": False}}
        for i in range(5)
    ]
    chemin = _corpus(tmp_path, lignes)
    runner = BenchmarkRunner(corpus_path=chemin)
    monkeypatch.setattr(
        runner.orchestrator, "analyser_texte",
        _async(lambda texte, source, sync_backend=True, date_reference=None: {"opportunities": []}),
    )

    # Horloge contrôlée : chaque appel dure exactement 1 seconde de plus.
    compteur = {"t": 0.0}
    def faux_perf_counter():
        compteur["t"] += 1.0
        return compteur["t"]
    monkeypatch.setattr(br_module.time, "perf_counter", faux_perf_counter)

    resultat = run(runner.run(limit=5))

    assert resultat["latency_median_seconds"] == 1.0
    assert resultat["latency_p95_seconds"] is not None
