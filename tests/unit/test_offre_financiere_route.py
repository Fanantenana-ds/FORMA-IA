"""Contrat HTTP M3 : les options financières atteignent l'orchestrateur."""

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.v1.endpoints import offre_ia
from app.utils.security import verify_api_key


class FauxOrchestrateur:
    def __init__(self):
        self.appels = []

    async def generate_financiere(self, offre_technique, options):
        self.appels.append((offre_technique, options))
        return {
            "reference": "ALT-OFF-FIN-TEST",
            "_review_id": "HITL-TEST-AM3-0001",
            "_review_status": "pending_review",
        }


def _client(orchestrateur):
    app = FastAPI()
    app.include_router(offre_ia.router, prefix="/api/v1")
    app.dependency_overrides[verify_api_key] = lambda: None
    app.dependency_overrides[offre_ia.get_offre_orchestrator] = lambda: orchestrateur
    return TestClient(app)


def test_generation_financiere_transmet_les_options():
    orchestrateur = FauxOrchestrateur()
    response = _client(orchestrateur).post(
        "/api/v1/ia/offres/generer-financiere",
        json={
            "offre_technique": {"reference": "ALT-OFF-TECH-2026-0001"},
            "options": {"nb_participants": 12, "type_formateur": "senior"},
        },
    )

    assert response.status_code == 200
    assert response.json()["review_id"] == "HITL-TEST-AM3-0001"
    assert orchestrateur.appels == [
        ({"reference": "ALT-OFF-TECH-2026-0001"}, {"nb_participants": 12, "type_formateur": "senior"})
    ]


def test_generation_financiere_sans_options_garde_la_compatibilite():
    orchestrateur = FauxOrchestrateur()
    response = _client(orchestrateur).post(
        "/api/v1/ia/offres/generer-financiere",
        json={"offre_technique": {"reference": "ALT-OFF-TECH-2026-0001"}},
    )

    assert response.status_code == 200
    assert orchestrateur.appels[0][1] == {}
