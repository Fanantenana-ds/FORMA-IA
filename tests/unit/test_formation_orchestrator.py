# ============================================================
# TESTS — app/orchestrator/formation_orchestrator.py (M5)
# ============================================================
# Aucun appel LLM/PDF/Google Forms réel : les 6 agents déjà instanciés par
# l'orchestrateur sont doublés méthode par méthode, comme pour les autres
# orchestrateurs de la suite.
# ============================================================

import asyncio

import pytest

import app.orchestrator.formation_orchestrator as fo_module
from app.orchestrator.formation_orchestrator import (
    FormationOrchestrator,
    get_formation_orchestrator,
)


def run(coro):
    return asyncio.run(coro)


def _async(fn):
    async def wrapper(*args, **kwargs):
        return fn(*args, **kwargs)
    return wrapper


@pytest.fixture
def orchestrateur():
    return FormationOrchestrator()


SESSION_INFO = {"id": 1, "titre": "Introduction à l'IA", "domaine": "IA"}


# ---- Agent 1 — génération des formulaires ----

def test_generate_forms_success(orchestrateur, monkeypatch):
    monkeypatch.setattr(
        orchestrateur.form_generator, "generate",
        _async(lambda session_info: {
            "inscription": {"questions": [{"id": "ins_01"}]},
            "test_avant": {"questions": []},
            "test_apres": {"questions": []},
            "satisfaction": {"questions": []},
        }),
    )
    resultat = run(orchestrateur.generate_forms(SESSION_INFO))
    assert len(resultat["inscription"]["questions"]) == 1


def test_generate_forms_agent_indisponible(orchestrateur):
    orchestrateur.form_generator = None
    with pytest.raises(RuntimeError, match="FormGeneratorService"):
        run(orchestrateur.generate_forms(SESSION_INFO))


def test_generate_forms_agent_leve_exception_est_relancee(orchestrateur, monkeypatch):
    async def echoue(session_info):
        raise ValueError("JSON invalide")

    monkeypatch.setattr(orchestrateur.form_generator, "generate", echoue)
    with pytest.raises(ValueError, match="JSON invalide"):
        run(orchestrateur.generate_forms(SESSION_INFO))


# ---- Agent 2 — analyse des niveaux ----

def test_analyze_levels_success(orchestrateur, monkeypatch):
    monkeypatch.setattr(
        orchestrateur.level_analyzer, "analyze",
        _async(lambda session_info, participants, corrige: {
            "statistiques": {"progression_absolue": 25.0},
            "recommandations": ["Reco 1", "Reco 2", "Reco 3"],
        }),
    )
    resultat = run(orchestrateur.analyze_levels(SESSION_INFO, [{"nom": "A"}], {"av_01": "A"}))
    assert resultat["statistiques"]["progression_absolue"] == 25.0


def test_analyze_levels_agent_indisponible(orchestrateur):
    orchestrateur.level_analyzer = None
    with pytest.raises(RuntimeError, match="LevelAnalyzerService"):
        run(orchestrateur.analyze_levels(SESSION_INFO, [], {}))


# ---- Agent 3 — analyse satisfaction ----

def test_analyze_satisfaction_success(orchestrateur, monkeypatch):
    monkeypatch.setattr(
        orchestrateur.satisfaction_analyzer, "analyze",
        _async(lambda session_info, responses: {
            "statistiques": {"notes": {"note_globale": 4.2}},
            "recommandations": ["Reco 1", "Reco 2", "Reco 3"],
        }),
    )
    resultat = run(orchestrateur.analyze_satisfaction(SESSION_INFO, [{"note": 5}]))
    assert resultat["statistiques"]["notes"]["note_globale"] == 4.2


def test_analyze_satisfaction_agent_indisponible(orchestrateur):
    orchestrateur.satisfaction_analyzer = None
    with pytest.raises(RuntimeError, match="SatisfactionAnalyzerService"):
        run(orchestrateur.analyze_satisfaction(SESSION_INFO, []))


# ---- Agent 4 — analyse présences (Python pur, synchrone) ----

def test_analyze_presences_success(orchestrateur, monkeypatch):
    monkeypatch.setattr(
        orchestrateur.presence_analyzer, "analyze",
        lambda session_info, participants, presences: {
            "statistiques": {"taux_presence_global": "85%"},
            "anomalies": [],
            "eligibles_attestation": ["A"],
        },
    )
    resultat = run(orchestrateur.analyze_presences(SESSION_INFO, [{"nom": "A"}], [{"date": "2026-10-15"}]))
    assert resultat["statistiques"]["taux_presence_global"] == "85%"


def test_analyze_presences_agent_indisponible(orchestrateur):
    orchestrateur.presence_analyzer = None
    with pytest.raises(RuntimeError, match="PresenceAnalyzerService"):
        run(orchestrateur.analyze_presences(SESSION_INFO, [], []))


# ---- Agent 5 — génération des attestations ----

def test_generate_attestations_aucun_eligible_court_circuite(orchestrateur):
    resultat = run(orchestrateur.generate_attestations(SESSION_INFO, []))
    assert resultat["success"] is True
    assert resultat["total_eligible"] == 0
    assert resultat["attestations"] == []


def test_generate_attestations_success(orchestrateur, monkeypatch):
    monkeypatch.setattr(
        orchestrateur.attestation_generator, "generate_batch_with_pdf",
        _async(lambda session_data, participants: {
            "success": True, "total_eligible": 1, "total_generated": 1, "total_failed": 0,
            "attestations": [{"numero_unique": "ALT-2026-IA-0001"}],
        }),
    )
    resultat = run(orchestrateur.generate_attestations(SESSION_INFO, [{"nom": "A"}]))
    assert resultat["total_generated"] == 1


def test_generate_attestations_agent_indisponible(orchestrateur):
    orchestrateur.attestation_generator = None
    with pytest.raises(RuntimeError, match="AttestationGeneratorService"):
        run(orchestrateur.generate_attestations(SESSION_INFO, [{"nom": "A"}]))


# ---- Agent 6 — rapport final ----

def test_generate_report_success(orchestrateur, monkeypatch):
    monkeypatch.setattr(
        orchestrateur.report_generator, "generate",
        _async(lambda session_data: {
            "recommandations": ["Reco 1", "Reco 2", "Reco 3"],
            "metadata": {"source": "llm"},
        }),
    )
    resultat = run(orchestrateur.generate_report(SESSION_INFO))
    assert resultat["metadata"]["source"] == "llm"


def test_generate_report_agent_indisponible(orchestrateur):
    orchestrateur.report_generator = None
    with pytest.raises(RuntimeError, match="ReportGeneratorService"):
        run(orchestrateur.generate_report(SESSION_INFO))


# ---- Agent 7 — RAG, non implémenté (V2) ----

def test_index_documents_non_implemente(orchestrateur):
    with pytest.raises(NotImplementedError):
        run(orchestrateur.index_documents({}))


# ---- Singleton ----

def test_get_formation_orchestrator_singleton(monkeypatch):
    monkeypatch.setattr(fo_module, "_orchestrator_instance", None)
    premiere = get_formation_orchestrator()
    seconde = get_formation_orchestrator()
    assert premiere is seconde
