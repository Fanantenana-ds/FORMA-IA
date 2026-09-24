# ============================================================
# TESTS — app/orchestrator/offre_orchestrator.py (M3)
# ============================================================
# Complète tests/unit/test_regenerer_et_sync_m3_prep.py (qui couvre déjà
# generate_complete/regenerate/synchroniser_backend en bout en bout).
# Ici : les 2 méthodes "agent seul" jamais testées (generate_technique,
# generate_financiere), les branches d'erreur, et le singleton.
# Aucun appel réseau/LLM réel.
# ============================================================

import asyncio

import pytest

import app.orchestrator.offre_orchestrator as oo_module
from app.orchestrator.offre_orchestrator import (
    OffreOrchestrator,
    get_offre_orchestrator,
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
    return OffreOrchestrator()


TDR = {"id": 1, "titre": "Introduction à l'IA"}
SESSION = {"client": "Ministère", "client_id": 1}


# ---- generate_technique (Agent M3-1 seul) ----

def test_generate_technique_success(orchestrateur, monkeypatch):
    monkeypatch.setattr(
        orchestrateur.offre_technique, "generate",
        _async(lambda tdr_data, session_info: {"reference": "ALT-OFF-TECH-2026-0001", "_review_id": "HITL-1"}),
    )
    resultat = run(orchestrateur.generate_technique(TDR, SESSION))
    assert resultat["reference"] == "ALT-OFF-TECH-2026-0001"


def test_generate_technique_agent_indisponible(orchestrateur):
    orchestrateur.offre_technique = None
    with pytest.raises(RuntimeError, match="M3-1"):
        run(orchestrateur.generate_technique(TDR, SESSION))


def test_generate_technique_exception_relancee(orchestrateur, monkeypatch):
    async def echoue(tdr_data, session_info):
        raise ValueError("Prompt invalide")

    monkeypatch.setattr(orchestrateur.offre_technique, "generate", echoue)
    with pytest.raises(ValueError, match="Prompt invalide"):
        run(orchestrateur.generate_technique(TDR, SESSION))


# ---- generate_financiere (Agent M3-2 seul) ----

def test_generate_financiere_success(orchestrateur, monkeypatch):
    monkeypatch.setattr(
        orchestrateur.offre_financiere, "generate",
        _async(lambda offre_technique, options: {
            "reference": "ALT-OFF-FIN-2026-0001",
            "recapitulatif": {"net_a_payer": 1150000},
            "_review_id": "HITL-2",
        }),
    )
    resultat = run(orchestrateur.generate_financiere({"reference": "TECH-1"}, {}))
    assert resultat["recapitulatif"]["net_a_payer"] == 1150000


def test_generate_financiere_agent_indisponible(orchestrateur):
    orchestrateur.offre_financiere = None
    with pytest.raises(RuntimeError, match="M3-2"):
        run(orchestrateur.generate_financiere({}, {}))


def test_generate_financiere_exception_relancee(orchestrateur, monkeypatch):
    async def echoue(offre_technique, options):
        raise ValueError("Grille tarifaire invalide")

    monkeypatch.setattr(orchestrateur.offre_financiere, "generate", echoue)
    with pytest.raises(ValueError, match="Grille tarifaire invalide"):
        run(orchestrateur.generate_financiere({}, {}))


# ---- _check_services (via generate_complete) ----

def test_generate_complete_les_deux_agents_manquants(orchestrateur):
    orchestrateur.offre_technique = None
    orchestrateur.offre_financiere = None
    with pytest.raises(RuntimeError) as exc_info:
        run(orchestrateur.generate_complete(TDR, SESSION))
    assert "M3-1" in str(exc_info.value)
    assert "M3-2" in str(exc_info.value)


def test_generate_complete_agent_leve_exception(orchestrateur, monkeypatch):
    async def echoue(tdr_data, session_info, feedback=None):
        raise RuntimeError("Groq indisponible")

    monkeypatch.setattr(orchestrateur.offre_technique, "generate", echoue)
    with pytest.raises(RuntimeError, match="Groq indisponible"):
        run(orchestrateur.generate_complete(TDR, SESSION))


# ---- Singleton ----

def test_get_offre_orchestrator_singleton(monkeypatch):
    monkeypatch.setattr(oo_module, "_offre_orchestrator_instance", None)
    premiere = get_offre_orchestrator()
    seconde = get_offre_orchestrator()
    assert premiere is seconde
