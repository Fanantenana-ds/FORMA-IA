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
    fusionner_rapports,
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


# ============================================================
# fusionner_rapports — pour --reprendre
# ============================================================

def test_fusion_equivaut_a_un_run_unique_sur_l_union(tmp_path, monkeypatch):
    lignes = [
        {"id": "c1", "raw_text": "Premier texte assez long pour la validation minimale du corpus.",
         "gold": {"is_opportunity": True, "domain": "ia", "budget_expected": "5M Ar"}},
        {"id": "c2", "raw_text": "Second texte assez long pour la validation minimale du corpus.",
         "gold": {"is_opportunity": False}},
        {"id": "c3", "raw_text": "Troisieme texte assez long pour la validation minimale du corpus.",
         "gold": {"is_opportunity": True, "domain": "data"}},
        {"id": "c4", "raw_text": "Quatrieme texte assez long pour la validation minimale du corpus.",
         "gold": {"is_opportunity": False}},
    ]

    async def analyse(texte, source, sync_backend=True, date_reference=None):
        if source == "c1":
            return {"opportunities": [{"domain": "ia", "budget": "5M Ar"}]}
        if source == "c3":
            return {"opportunities": [{"domain": "ia"}]}  # "data" mal classé "ia"
        return {"opportunities": []}

    # Run UNIQUE sur les 4 entrées
    chemin_complet = _corpus(tmp_path, lignes)
    runner_complet = BenchmarkRunner(corpus_path=chemin_complet)
    monkeypatch.setattr(runner_complet.orchestrator, "analyser_texte", analyse)
    rapport_complet = run(runner_complet.run(limit=4))

    # Deux runs séparés (2 + 2), fusionnés
    chemin_a = tmp_path / "a.jsonl"
    chemin_a.write_text("\n".join(json.dumps(l, ensure_ascii=False) for l in lignes[:2]), encoding="utf-8")
    chemin_b = tmp_path / "b.jsonl"
    chemin_b.write_text("\n".join(json.dumps(l, ensure_ascii=False) for l in lignes[2:]), encoding="utf-8")
    runner_a = BenchmarkRunner(corpus_path=chemin_a)
    runner_b = BenchmarkRunner(corpus_path=chemin_b)
    monkeypatch.setattr(runner_a.orchestrator, "analyser_texte", analyse)
    monkeypatch.setattr(runner_b.orchestrator, "analyser_texte", analyse)
    rapport_a = run(runner_a.run(limit=2))
    rapport_b = run(runner_b.run(limit=2))

    rapport_fusionne = fusionner_rapports([rapport_a, rapport_b])

    for cle in (
        "confusion_matrix", "precision_detection", "recall_detection", "f1_detection",
        "domain_confusion_matrix", "domain_classification_accuracy", "f1_macro_domain",
        "extraction_par_champ", "extraction_accuracy", "hallucinated_values",
        "corpus_size_tested", "llm_fallback_count", "model_error_count",
    ):
        assert rapport_fusionne[cle] == rapport_complet[cle], f"écart sur {cle}"

    assert len(rapport_fusionne["details"]) == 4


def test_fusion_d_un_seul_rapport_le_retourne_inchange():
    rapport = {"corpus_size_tested": 1, "details": []}
    assert fusionner_rapports([rapport]) is rapport


def test_fusion_sans_rapport_leve_une_erreur_claire():
    with pytest.raises(ValueError, match="Aucun rapport"):
        fusionner_rapports([])


# ============================================================
# Mesure déterministe séparée — ClassificationService seul (point 4)
# ============================================================

def test_mesure_deterministe_ne_touche_jamais_au_llm(tmp_path, monkeypatch):
    """Aucun appel à analyser_texte (donc au LLM) : la mesure ne porte que
    sur ClassificationService, en Python pur."""
    lignes = [
        {"id": "c1", "raw_text": "Formation en intelligence artificielle pour agents publics.",
         "gold": {"is_opportunity": True, "domain": "ia"}},
        {"id": "c2", "raw_text": "Cette annonce ne concerne pas une opportunite ALTIORA.",
         "gold": {"is_opportunity": False}},  # pas de domaine -> ignoré
    ]
    chemin = _corpus(tmp_path, lignes)
    runner = BenchmarkRunner(corpus_path=chemin)

    async def interdit(*a, **kw):
        raise AssertionError("le LLM ne doit jamais être appelé par cette mesure")
    monkeypatch.setattr(runner.orchestrator, "analyser_texte", interdit)
    monkeypatch.setattr(runner.orchestrator.llm_service, "analyze", interdit)

    resultat = runner.mesurer_classification_deterministe(limit=2)

    assert resultat["domain_total"] == 1  # seul c1 a un domaine gold
    assert resultat["domain_correct"] == 1
    assert resultat["domain_accuracy"] == 1.0


def test_mesure_deterministe_est_reproductible(tmp_path):
    """Aucune dépendance à l'heure/au hasard : deux appels identiques."""
    lignes = [{"id": "c1", "raw_text": "Formation en intelligence artificielle pour agents publics.",
               "gold": {"is_opportunity": True, "domain": "ia"}}]
    chemin = _corpus(tmp_path, lignes)
    runner = BenchmarkRunner(corpus_path=chemin)

    resultat_1 = runner.mesurer_classification_deterministe(limit=1)
    resultat_2 = runner.mesurer_classification_deterministe(limit=1)

    assert resultat_1 == resultat_2


def test_run_accepte_des_entries_precalculees_sans_relire_le_fichier(tmp_path, monkeypatch):
    """Pour scripts/benchmark_m1.py : filtrer par split/reprise AVANT
    d'appeler run(), sans dépendre du contenu réel du fichier corpus."""
    chemin = _corpus(tmp_path, [{"id": "ignore-moi", "raw_text": "x" * 30, "gold": {"is_opportunity": False}}])
    runner = BenchmarkRunner(corpus_path=chemin)
    monkeypatch.setattr(
        runner.orchestrator, "analyser_texte",
        _async(lambda texte, source, sync_backend=True, date_reference=None: {"opportunities": []}),
    )

    entries_forcees = [{"id": "c-force", "raw_text": "texte force" * 3, "gold": {"is_opportunity": False}}]
    resultat = run(runner.run(limit=10, entries=entries_forcees))

    assert resultat["corpus_size_tested"] == 1
    assert resultat["details"][0]["id"] == "c-force"


def test_pause_secondes_attend_entre_chaque_document(tmp_path, monkeypatch):
    lignes = [
        {"id": "c1", "raw_text": "x" * 30, "gold": {"is_opportunity": False}},
        {"id": "c2", "raw_text": "y" * 30, "gold": {"is_opportunity": False}},
    ]
    chemin = _corpus(tmp_path, lignes)
    runner = BenchmarkRunner(corpus_path=chemin)
    monkeypatch.setattr(
        runner.orchestrator, "analyser_texte",
        _async(lambda texte, source, sync_backend=True, date_reference=None: {"opportunities": []}),
    )

    pauses = []
    async def fausse_attente(secondes):
        pauses.append(secondes)
    monkeypatch.setattr(br_module.asyncio, "sleep", fausse_attente)

    run(runner.run(limit=2, pause_secondes=0.5))

    assert pauses == [0.5, 0.5]  # une pause après CHAQUE document (y compris le dernier, sans risque)


def test_mesure_deterministe_signale_les_erreurs_de_domaine(tmp_path):
    lignes = [{"id": "c1", "raw_text": "Mission de developpement web et mobile pour une PME.",
               "gold": {"is_opportunity": True, "domain": "ia"}}]  # gold FAUX volontairement
    chemin = _corpus(tmp_path, lignes)
    runner = BenchmarkRunner(corpus_path=chemin)

    resultat = runner.mesurer_classification_deterministe(limit=1)

    assert resultat["domain_correct"] == 0
    assert resultat["domain_confusion_matrix"]["ia"]["developpement"] == 1
