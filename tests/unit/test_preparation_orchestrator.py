# ============================================================
# TESTS — app/orchestrator/preparation_orchestrator.py
# ============================================================
# Complète tests/unit/test_regenerer_et_sync_m3_prep.py (qui couvre déjà
# generate_complete/regenerate/synchroniser_backend en bout en bout).
# Ici : les 2 méthodes "seules" jamais testées (calculer_budget, generer_edt),
# les branches d'erreur de regenerate(), _build_dates, et le singleton.
# Aucun appel réseau/LLM réel.
# ============================================================

import asyncio

import pytest

import app.orchestrator.preparation_orchestrator as po_module
from app.orchestrator.preparation_orchestrator import (
    PreparationOrchestrator,
    get_preparation_orchestrator,
)
from app.services.hitl import hitl_helper
from app.services.backend_sync import review_sync


def run(coro):
    return asyncio.run(coro)


def _async(fn):
    async def wrapper(*args, **kwargs):
        return fn(*args, **kwargs)
    return wrapper


@pytest.fixture(autouse=True)
def isole(monkeypatch, tmp_path):
    monkeypatch.setattr(hitl_helper, "STORAGE_PATH", tmp_path / "hitl_reviews.json")
    monkeypatch.setattr(review_sync, "REGISTRY_PATH", tmp_path / "registry.json")


@pytest.fixture
def orchestrateur():
    return PreparationOrchestrator()


FORMATEUR = {"nom": "M. RANAIVOSOA", "tarif_journalier": 500000}
SALLE = {"nom": "Salle A", "tarif_journalier": 200000}


# ---- calculer_budget (seul) ----

def test_calculer_budget_success(orchestrateur, monkeypatch):
    monkeypatch.setattr(
        orchestrateur.budget_calculator, "calculer",
        lambda **kwargs: {"cout_total": 1500000, "cout_formateur": 1000000},
    )
    resultat = orchestrateur.calculer_budget(FORMATEUR, SALLE, nb_jours=2, nb_participants=20)
    assert resultat["cout_total"] == 1500000


def test_calculer_budget_agent_indisponible(orchestrateur):
    orchestrateur.budget_calculator = None
    with pytest.raises(RuntimeError, match="BudgetCalculatorService"):
        orchestrateur.calculer_budget(FORMATEUR, SALLE, nb_jours=2, nb_participants=20)


def test_calculer_budget_exception_relancee(orchestrateur, monkeypatch):
    def echoue(**kwargs):
        raise ValueError("tarif_journalier manquant")

    monkeypatch.setattr(orchestrateur.budget_calculator, "calculer", echoue)
    with pytest.raises(ValueError, match="tarif_journalier manquant"):
        orchestrateur.calculer_budget({}, {}, nb_jours=2, nb_participants=20)


# ---- generer_edt (seul) ----

def test_generer_edt_success(orchestrateur, monkeypatch):
    monkeypatch.setattr(
        orchestrateur.edt_generator, "generate",
        _async(lambda **kwargs: {"jours": [{"numero": 1}], "metadata": {"source": "fallback_template"}}),
    )
    resultat = run(orchestrateur.generer_edt(
        "Introduction à l'IA", [{"titre": "Module 1", "duree": "3h"}], ["2026-10-15"],
    ))
    assert len(resultat["jours"]) == 1


def test_generer_edt_agent_indisponible(orchestrateur):
    orchestrateur.edt_generator = None
    with pytest.raises(RuntimeError, match="EDTGeneratorService"):
        run(orchestrateur.generer_edt("x", [], []))


def test_generer_edt_exception_relancee(orchestrateur, monkeypatch):
    async def echoue(**kwargs):
        raise ValueError("Dates invalides")

    monkeypatch.setattr(orchestrateur.edt_generator, "generate", echoue)
    with pytest.raises(ValueError, match="Dates invalides"):
        run(orchestrateur.generer_edt("x", [], []))


# ---- _check_services (via generate_complete) ----

def test_generate_complete_les_deux_services_manquants(orchestrateur):
    orchestrateur.budget_calculator = None
    orchestrateur.edt_generator = None
    with pytest.raises(RuntimeError) as exc_info:
        run(orchestrateur.generate_complete({}, {}, {}))
    assert "BudgetCalculatorService" in str(exc_info.value)
    assert "EDTGeneratorService" in str(exc_info.value)


# ---- regenerate — branches d'erreur ----

def test_regenerate_review_introuvable(orchestrateur):
    with pytest.raises(ValueError, match="introuvable"):
        run(orchestrateur.regenerate("HITL-INEXISTANT", "Feedback quelconque"))


def test_regenerate_review_non_rejete(orchestrateur):
    review_id = hitl_helper.create_review(
        agent_id="agent_preparation", data={"_inputs": {}}, summary="x", criticity="medium",
    )
    with pytest.raises(ValueError, match="pas rejeté"):
        run(orchestrateur.regenerate(review_id, "Feedback quelconque"))


def test_regenerate_review_autre_agent(orchestrateur):
    review_id = hitl_helper.create_review(
        agent_id="agent_m3_complete", data={"_inputs": {}}, summary="x", criticity="medium",
    )
    hitl_helper.reject_review(review_id, "Rejeté pour test")
    with pytest.raises(ValueError, match="pas par la Préparation"):
        run(orchestrateur.regenerate(review_id, "Feedback quelconque"))


def test_regenerate_review_sans_inputs_memorises(orchestrateur):
    review_id = hitl_helper.create_review(
        agent_id="agent_preparation", data={}, summary="x", criticity="medium",
    )
    hitl_helper.reject_review(review_id, "Rejeté pour test")
    with pytest.raises(ValueError, match="générer-complet|generer-complet"):
        run(orchestrateur.regenerate(review_id, "Feedback quelconque"))


# ---- _build_dates ----

def test_build_dates_plage_normale():
    dates = PreparationOrchestrator._build_dates("2026-10-15", "2026-10-16")
    assert dates == ["2026-10-15", "2026-10-16"]


def test_build_dates_format_invalide_retombe_sur_date_debut():
    dates = PreparationOrchestrator._build_dates("pas-une-date", "non-plus")
    assert dates == ["pas-une-date"]


# ---- Singleton ----

def test_get_preparation_orchestrator_singleton(monkeypatch):
    monkeypatch.setattr(po_module, "_preparation_orchestrator_instance", None)
    premiere = get_preparation_orchestrator()
    seconde = get_preparation_orchestrator()
    assert premiere is seconde
