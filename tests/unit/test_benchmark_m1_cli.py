# tests/unit/test_benchmark_m1_cli.py
# ============================================================
# Étape C point 3/5 (mission "Préparation soutenance") — CLI benchmark_m1.py
# ============================================================
# scripts/ n'a pas de __init__.py : chargement par chemin de fichier.
# Aucun réseau réel : BenchmarkRunner.run() est doublé (déjà testé
# séparément dans test_benchmark_rapport_complet.py) ; input() doublé
# (aucune confirmation réelle attendue).
# ============================================================

import asyncio
import importlib.util
import json
from pathlib import Path

import pytest

RACINE = Path(__file__).resolve().parents[2]


def _charger_module():
    chemin = RACINE / "scripts" / "benchmark_m1.py"
    spec = importlib.util.spec_from_file_location("benchmark_m1_cli_sous_test", chemin)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


cli = _charger_module()


def run(coro):
    return asyncio.run(coro)


# ============================================================
# _filtrer_par_split
# ============================================================

def test_filtrer_par_split_none_retourne_tout():
    entries = [{"id": "a"}, {"id": "b"}]
    assert cli._filtrer_par_split(entries, None) == entries


def test_filtrer_par_split_aucun_champ_avertit_et_retourne_tout(capsys):
    entries = [{"id": "a"}, {"id": "b"}]
    resultat = cli._filtrer_par_split(entries, "dev")
    assert resultat == entries
    assert "ignoré" in capsys.readouterr().out


def test_filtrer_par_split_filtre_reellement():
    entries = [{"id": "a", "split": "dev"}, {"id": "b", "split": "test"}]
    assert cli._filtrer_par_split(entries, "dev") == [{"id": "a", "split": "dev"}]


# ============================================================
# _trouver_dernier_resultat
# ============================================================

def test_trouver_dernier_resultat_absent(tmp_path, monkeypatch):
    monkeypatch.setattr(cli, "RESULTS_DIR", tmp_path)
    assert cli._trouver_dernier_resultat("corpus_v1", None) is None


def test_trouver_dernier_resultat_prend_le_plus_recent(tmp_path, monkeypatch):
    monkeypatch.setattr(cli, "RESULTS_DIR", tmp_path)
    (tmp_path / "benchmark_m1_corpus_v1_20260101_000000.json").write_text("{}", encoding="utf-8")
    (tmp_path / "benchmark_m1_corpus_v1_20260926_120000.json").write_text("{}", encoding="utf-8")

    resultat = cli._trouver_dernier_resultat("corpus_v1", None)
    assert resultat.name == "benchmark_m1_corpus_v1_20260926_120000.json"


def test_trouver_dernier_resultat_respecte_le_split(tmp_path, monkeypatch):
    monkeypatch.setattr(cli, "RESULTS_DIR", tmp_path)
    (tmp_path / "benchmark_m1_corpus_v1_dev_20260101_000000.json").write_text("{}", encoding="utf-8")
    (tmp_path / "benchmark_m1_corpus_v1_test_20260102_000000.json").write_text("{}", encoding="utf-8")

    assert cli._trouver_dernier_resultat("corpus_v1", "dev").name.endswith("dev_20260101_000000.json")


# ============================================================
# main() — bout en bout, LLM/réseau doublés
# ============================================================

RAPPORT_MINIMAL = {
    "corpus_path": "corpus.jsonl",
    "corpus_size_tested": 1,
    "confusion_matrix": {"true_positives": 1, "false_positives": 0, "false_negatives": 0, "true_negatives": 0},
    "precision_detection": 1.0, "recall_detection": 1.0,
    "f1_detection": 1.0, "domain_classification_accuracy": None, "f1_macro_domain": None,
    "domain_confusion_matrix": {},
    "extraction_accuracy": None,
    "extraction_par_champ": {
        "budget": {"correct": 0, "total": 0, "accuracy": None},
        "deadline": {"correct": 0, "total": 0, "accuracy": None},
        "organizer": {"correct": 0, "total": 0, "accuracy": None},
    },
    "hallucinated_values": {"budget": 0, "deadline": 0, "organizer": 0, "total": 0},
    "average_latency_seconds": 0.1, "latency_median_seconds": 0.1, "latency_p95_seconds": 0.1,
    "llm_fallback_count": 0, "model_error_count": 0,
    "configuration_snapshot": {"fournisseur_llm": None, "modele_llm": None,
                                "empreinte_prompts_m1": "abc", "date_execution": "2026-09-26T00:00:00"},
    "cdc_targets": {"precision_target": 0.85, "extraction_target": 0.90, "latency_target_seconds": 3.0},
    "meets_cdc_precision": True, "meets_cdc_extraction": False, "meets_cdc_latency": True,
    "details": [{"id": "c1", "expected_is_opportunity": True, "predicted_is_opportunity": True,
                 "correct_detection": True, "expected_domain": None, "predicted_domain": None,
                 "latency_seconds": 0.1}],
}


@pytest.fixture
def corpus_minimal(tmp_path):
    chemin = tmp_path / "corpus.jsonl"
    chemin.write_text(
        json.dumps({"id": "c1", "raw_text": "x" * 30, "gold": {"is_opportunity": True}}),
        encoding="utf-8",
    )
    return chemin


def test_main_annule_si_confirmation_refusee(monkeypatch, corpus_minimal, tmp_path):
    monkeypatch.setattr(cli, "RESULTS_DIR", tmp_path / "results")
    monkeypatch.setattr("builtins.input", lambda *a: "n")
    monkeypatch.setattr(cli.sys, "argv", ["benchmark_m1.py", "--corpus", str(corpus_minimal)])

    appele = {"n": False}
    async def jamais_appele(self, **kw):
        appele["n"] = True
        return RAPPORT_MINIMAL
    monkeypatch.setattr(cli.BenchmarkRunner, "run", jamais_appele)

    ok = run(cli.main())

    assert ok is False
    assert appele["n"] is False  # AUCUN appel réel tenté


def test_main_ecrit_json_et_csv_apres_confirmation(monkeypatch, corpus_minimal, tmp_path):
    dossier_resultats = tmp_path / "results"
    monkeypatch.setattr(cli, "RESULTS_DIR", dossier_resultats)
    monkeypatch.setattr("builtins.input", lambda *a: "o")
    monkeypatch.setattr(cli.sys, "argv", ["benchmark_m1.py", "--corpus", str(corpus_minimal)])

    async def faux_run(self, **kw):
        return RAPPORT_MINIMAL
    monkeypatch.setattr(cli.BenchmarkRunner, "run", faux_run)

    ok = run(cli.main())

    assert ok is True
    fichiers = list(dossier_resultats.glob("*.json"))
    assert len(fichiers) == 1
    contenu = json.loads(fichiers[0].read_text(encoding="utf-8"))
    assert contenu["corpus_size_tested"] == 1
    assert list(dossier_resultats.glob("*.csv"))


def test_main_reprendre_fusionne_avec_le_resultat_precedent(monkeypatch, corpus_minimal, tmp_path):
    dossier_resultats = tmp_path / "results"
    dossier_resultats.mkdir()
    rapport_precedent = {**RAPPORT_MINIMAL, "corpus_size_tested": 5,
                         "details": [{"id": "deja-fait", "latency_seconds": 0.1}]}
    (dossier_resultats / "benchmark_m1_corpus_20260101_000000.json").write_text(
        json.dumps(rapport_precedent), encoding="utf-8",
    )
    monkeypatch.setattr(cli, "RESULTS_DIR", dossier_resultats)
    monkeypatch.setattr("builtins.input", lambda *a: "o")
    monkeypatch.setattr(
        cli.sys, "argv",
        ["benchmark_m1.py", "--corpus", str(corpus_minimal), "--reprendre"],
    )

    recu = {}
    async def capter_run(self, **kw):
        recu.update(kw)
        return RAPPORT_MINIMAL
    monkeypatch.setattr(cli.BenchmarkRunner, "run", capter_run)

    ok = run(cli.main())

    assert ok is True
    # "c1" (seule entrée du corpus) n'était PAS dans le rapport précédent -> traité
    assert [e["id"] for e in recu["entries"]] == ["c1"]

    fichiers = sorted(dossier_resultats.glob("*.json"))
    dernier = json.loads(fichiers[-1].read_text(encoding="utf-8"))
    # fusion : corpus_size_tested combiné (5 précédent + 1 nouveau)
    assert dernier["corpus_size_tested"] == 6
    assert {d["id"] for d in dernier["details"]} == {"deja-fait", "c1"}


def test_main_rien_a_traiter_si_tout_deja_fait(monkeypatch, corpus_minimal, tmp_path):
    dossier_resultats = tmp_path / "results"
    dossier_resultats.mkdir()
    rapport_precedent = {**RAPPORT_MINIMAL, "details": [{"id": "c1", "latency_seconds": 0.1}]}
    (dossier_resultats / "benchmark_m1_corpus_20260101_000000.json").write_text(
        json.dumps(rapport_precedent), encoding="utf-8",
    )
    monkeypatch.setattr(cli, "RESULTS_DIR", dossier_resultats)
    monkeypatch.setattr(
        cli.sys, "argv",
        ["benchmark_m1.py", "--corpus", str(corpus_minimal), "--reprendre"],
    )

    async def jamais_appele(self, **kw):
        raise AssertionError("run() ne doit jamais être appelé : tout est déjà traité")
    monkeypatch.setattr(cli.BenchmarkRunner, "run", jamais_appele)

    ok = run(cli.main())

    assert ok is True  # rien à faire n'est pas un échec
