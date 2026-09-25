"""
Tests du contrôle de santé des modules IA (GET /health/ia).

Contexte : un paquet manquant (pandas) désactivait les Agents 2 et 3 sans
erreur — seulement un avertissement dans les logs — et les routes
/ia/formations/health répondaient « success: true » avec 4/7 agents.

Exécution :
    python -m pytest tests/unit/test_ia_health.py -q
"""

import logging

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services import facturation, formations, ia_health, offres, preparation


@pytest.fixture
def client():
    return TestClient(app)


def test_tous_les_agents_requis_sont_charges_dans_cet_environnement():
    """
    Garde-fou d'installation : échoue si une dépendance manque dans le venv
    (c'est exactement ce que pandas absent aurait déclenché).
    """
    etat = ia_health.collecter()

    assert etat["manquants"] == [], f"Agents indisponibles : {etat['manquants']}"
    assert etat["status"] == "healthy"


def test_m5_expose_6_agents_actifs_sur_7():
    m5 = ia_health.collecter()["modules"]["M5"]

    assert (m5["charges"], m5["total"]) == (6, 7)
    assert m5["manquants"] == []          # l'Agent 7 (RAG V2) est optionnel


def test_les_cinq_modules_sont_couverts():
    # C3 (RAG) ajouté à l'Étape H de la mission RAG (2026-09-25) : le
    # module est livré (routes, chat, portfolio, syllabus, questions) et
    # suit désormais son état via get_package_status() comme les autres.
    assert set(ia_health.collecter()["modules"]) == {"M5", "M3", "PREPARATION", "M7", "C3"}


def test_un_agent_requis_manquant_donne_degraded(monkeypatch):
    monkeypatch.setattr(formations, "LevelAnalyzerService", None)   # simule pandas absent

    etat = ia_health.collecter()

    assert etat["status"] == "degraded"
    assert etat["manquants"] == ["M5 — Agent 2 — LevelAnalyzer"]
    assert etat["modules"]["M5"]["charges"] == 5


def test_l_agent_7_absent_n_est_pas_une_degradation(monkeypatch):
    monkeypatch.setattr(formations, "KnowledgeBaseService", None)

    assert ia_health.collecter()["status"] == "healthy"


def test_un_service_m3_ou_preparation_manquant_est_signale(monkeypatch):
    monkeypatch.setattr(offres, "OffreFinanciereGeneratorService", None)
    monkeypatch.setattr(preparation, "EDTGeneratorService", None)

    manquants = ia_health.collecter()["manquants"]

    assert any(m.startswith("M3 —") for m in manquants)
    assert any(m.startswith("PREPARATION —") for m in manquants)


def test_agent_m7_manquant_est_signale(monkeypatch):
    monkeypatch.setattr(facturation, "RelanceGeneratorService", None)

    etat = ia_health.collecter()

    assert etat["status"] == "degraded"
    assert any(m.startswith("M7 —") for m in etat["manquants"])


def test_route_health_ia_sain(client):
    reponse = client.get("/health/ia")

    assert reponse.status_code == 200
    corps = reponse.json()
    assert corps["status"] == "healthy" and corps["manquants"] == []
    assert corps["modules"]["M5"]["charges"] == 6
    assert "timestamp" in corps


def test_route_health_ia_degradee_reste_en_http_200(client, monkeypatch):
    monkeypatch.setattr(formations, "SatisfactionAnalyzerService", None)

    reponse = client.get("/health/ia")

    assert reponse.status_code == 200
    assert reponse.json()["status"] == "degraded"
    assert "Agent 3" in reponse.json()["manquants"][0]


def test_la_route_health_simple_est_inchangee(client):
    assert client.get("/health").json()["status"] == "healthy"


def test_alerte_error_au_demarrage_quand_un_agent_manque(monkeypatch, caplog):
    monkeypatch.setattr(formations, "LevelAnalyzerService", None)

    with caplog.at_level(logging.INFO, logger=ia_health.logger.name):
        etat = ia_health.journaliser_au_demarrage()

    erreurs = [r for r in caplog.records if r.levelno == logging.ERROR]
    assert etat["status"] == "degraded"
    assert len(erreurs) == 1 and "Agent 2" in erreurs[0].getMessage()


def test_pas_d_alerte_error_quand_tout_est_charge(caplog):
    with caplog.at_level(logging.INFO, logger=ia_health.logger.name):
        ia_health.journaliser_au_demarrage()

    assert not [r for r in caplog.records if r.levelno >= logging.ERROR]
