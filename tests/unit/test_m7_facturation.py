"""
Tests M7 — Facturation IA (Agent de relance).

Aucun appel réseau : faux LLM, faux Backend (facture_sync.fetch_facture
piégé), store HITL dans un dossier temporaire.

Exécution :
    python -m pytest tests/unit/test_m7_facturation.py -q
"""

import asyncio
from datetime import date, timedelta

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.v1.endpoints import facture_ia
from app.orchestrator.facturation_orchestrator import FacturationOrchestrator
from app.services.backend_sync import facture_sync
from app.services.backend_sync.facture_calculator_service import FactureCalculatorService
from app.services.facturation.relance_generator_service import RelanceGeneratorService
from app.services.hitl import hitl_helper

AUJOURDHUI = date(2026, 9, 22)


def run(coro):
    return asyncio.run(coro)


@pytest.fixture(autouse=True)
def store_hitl_temporaire(monkeypatch, tmp_path):
    monkeypatch.setattr(hitl_helper, "STORAGE_PATH", tmp_path / "hitl_reviews.json")


class FauxLLM:
    """Faux LLMProvider (interface app.services.llm.LLMProvider.generate)."""

    def __init__(self, contenu=None, finish="stop", erreur=None):
        self.contenu = contenu
        self.finish = finish
        self.erreur = erreur
        self.appels = 0

    async def generate(self, system_prompt, user_prompt, temperature=0.4,
                       max_tokens=4000, json_mode=True):
        self.appels += 1
        if self.erreur:
            raise self.erreur
        import json
        contenu = self.contenu if isinstance(self.contenu, str) else json.dumps(self.contenu)
        return {"content": contenu, "finish_reason": self.finish,
                "usage": {}, "model": "faux", "provider": "faux"}


def facture(numero="FACT-2026-0001", client="Client A", montant_ttc=1_000_000.0,
            date_echeance=None, paiements=None):
    return {
        "id": "f" * 8 + "-0000-0000-0000-000000000000",
        "numero": numero,
        "client": client,
        "montant_ttc": montant_ttc,
        "date_echeance": date_echeance.isoformat() if date_echeance else None,
        "paiements": paiements or [],
    }


@pytest.fixture
def service():
    s = RelanceGeneratorService()
    s.llm = None
    return s


# ============================================================
# Calcul déterministe : jours de retard / niveau
# ============================================================

def test_pas_de_retard_donne_niveau_none(service):
    assert service.calculer_niveau(0) is None
    assert service.calculer_niveau(-5) is None


@pytest.mark.parametrize("jours, niveau", [
    (1, 1), (14, 1), (15, 2), (44, 2), (45, 3), (100, 3),
])
def test_seuils_d_escalade(service, jours, niveau):
    assert service.calculer_niveau(jours) == niveau


def test_jours_de_retard_calcules_depuis_l_echeance(service):
    echeance = AUJOURDHUI - timedelta(days=10)
    assert service.calculer_jours_retard(echeance.isoformat(), aujourdhui=AUJOURDHUI) == 10


def test_jours_de_retard_ne_devient_jamais_negatif(service):
    echeance = AUJOURDHUI + timedelta(days=10)  # échéance future
    assert service.calculer_jours_retard(echeance.isoformat(), aujourdhui=AUJOURDHUI) == 0


def test_sans_echeance_zero_jour_de_retard(service):
    assert service.calculer_jours_retard(None) == 0


def test_echeance_illisible_zero_jour_de_retard(service):
    assert service.calculer_jours_retard("pas une date") == 0


# ============================================================
# calculer_reste_du (déjà existant, régression)
# ============================================================

def test_reste_du_deduit_les_paiements():
    f = facture(montant_ttc=1000.0, paiements=[{"montant": 300.0}, {"montant": 200.0}])
    assert FactureCalculatorService.calculer_reste_du(f) == 500.0


def test_reste_du_jamais_negatif():
    f = facture(montant_ttc=1000.0, paiements=[{"montant": 5000.0}])
    assert FactureCalculatorService.calculer_reste_du(f) == 0.0


# ============================================================
# Génération de la relance (LLM, repli, chiffres non modifiables)
# ============================================================

FACTS = {
    "numero": "FACT-2026-0042", "client": "Ministère X",
    "montant_restant_du": 250_000.0, "devise": "MGA",
    "date_echeance": "2026-09-01", "jours_retard": 21, "niveau": 2,
}


def test_sans_llm_utilise_le_gabarit_python(service):
    resultat = run(service.generate(FACTS))

    assert resultat["metadata"]["source"] == "fallback_template"
    assert resultat["niveau"] == 2 and resultat["ton"] == "relance ferme"
    assert "FACT-2026-0042" in resultat["texte"]
    assert "250000.0" in resultat["texte"] or "250000" in resultat["texte"]


@pytest.mark.parametrize("niveau", [1, 2, 3])
def test_le_gabarit_couvre_les_3_niveaux(service, niveau):
    resultat = run(service.generate({**FACTS, "niveau": niveau}))

    assert resultat["texte"]
    assert resultat["ton"] == {1: "rappel courtois", 2: "relance ferme",
                               3: "mise en demeure formelle"}[niveau]


def test_le_llm_redige_mais_ne_change_pas_les_faits(service):
    service.llm = FauxLLM({
        "objet": "Relance urgente",
        "texte": "Texte rédigé par le LLM, mentionne FACT-2026-0042.",
    })

    resultat = run(service.generate(FACTS))

    assert resultat["metadata"]["source"] == "llm"
    assert resultat["objet"] == "Relance urgente"
    assert resultat["faits"] == FACTS          # jamais recalculés côté service
    assert resultat["niveau"] == FACTS["niveau"]


def test_le_llm_sans_objet_recoit_un_objet_par_defaut(service):
    service.llm = FauxLLM({"texte": "Corps de la relance."})

    resultat = run(service.generate(FACTS))

    assert resultat["objet"] == "Relance facture FACT-2026-0042 — relance ferme"


@pytest.mark.parametrize("faux", [
    FauxLLM(erreur=RuntimeError("quota")),
    FauxLLM("pas du json"),
    FauxLLM({"objet": "x"}),                       # pas de texte exploitable
    FauxLLM({"texte": "trop tard"}, finish="length"),
])
def test_llm_en_echec_bascule_sur_le_gabarit(service, faux):
    service.llm = faux

    resultat = run(service.generate(FACTS))

    assert resultat["metadata"]["source"] == "fallback_template"
    assert resultat["texte"]


# ============================================================
# Orchestrateur — cas "pas de relance nécessaire"
# ============================================================

@pytest.fixture
def orchestrator(monkeypatch):
    orch = FacturationOrchestrator()
    orch.relance_generator.llm = None       # jamais de vrai appel Groq
    return orch


def test_facture_deja_soldee_aucune_relance(orchestrator, monkeypatch):
    async def faux_fetch(facture_id):
        return facture(montant_ttc=1000.0, paiements=[{"montant": 1000.0}],
                       date_echeance=AUJOURDHUI - timedelta(days=10))

    monkeypatch.setattr(facture_sync, "fetch_facture", faux_fetch)

    resultat = run(orchestrator.generer_relance("id-quelconque"))

    assert resultat == {
        "success": True, "necessaire": False,
        "raison": "Facture déjà soldée (aucun montant restant dû).",
        "facture_id": "id-quelconque",
    }


def test_echeance_non_depassee_aucune_relance(orchestrator, monkeypatch):
    async def faux_fetch(facture_id):
        return facture(date_echeance=date.today() + timedelta(days=5))

    monkeypatch.setattr(facture_sync, "fetch_facture", faux_fetch)

    resultat = run(orchestrator.generer_relance("id-quelconque"))

    assert resultat["necessaire"] is False
    assert "non dépassée" in resultat["raison"]


def test_facture_introuvable_leve_value_error(orchestrator, monkeypatch):
    async def faux_fetch(facture_id):
        return None

    monkeypatch.setattr(facture_sync, "fetch_facture", faux_fetch)

    with pytest.raises(ValueError, match="introuvable"):
        run(orchestrator.generer_relance("id-inconnu"))


# ============================================================
# Orchestrateur — relance générée + HITL
# ============================================================

def test_relance_necessaire_cree_une_review_hitl_critique(orchestrator, monkeypatch):
    async def faux_fetch(facture_id):
        return facture(
            numero="FACT-2026-0099", client="Client B", montant_ttc=500_000.0,
            date_echeance=date.today() - timedelta(days=50),   # niveau 3
        )

    monkeypatch.setattr(facture_sync, "fetch_facture", faux_fetch)

    resultat = run(orchestrator.generer_relance("f-0099"))

    assert resultat["necessaire"] is True
    assert resultat["niveau"] == 3
    assert resultat["_review_status"] == "pending_review"
    assert resultat["_review_id"].startswith("HITL-")

    review = hitl_helper.get_review(resultat["_review_id"])
    assert review["agent_id"] == "agent_m7_relance"
    assert review["criticity"] == "critical"       # contenu envoyé à un vrai client


def test_niveau_1_pour_un_leger_retard(orchestrator, monkeypatch):
    async def faux_fetch(facture_id):
        return facture(date_echeance=date.today() - timedelta(days=3))

    monkeypatch.setattr(facture_sync, "fetch_facture", faux_fetch)

    resultat = run(orchestrator.generer_relance("f-0001"))

    assert resultat["niveau"] == 1


def test_agent_indisponible_leve_runtime_error(monkeypatch):
    orch = FacturationOrchestrator()
    orch.relance_generator = None

    with pytest.raises(RuntimeError):
        run(orch.generer_relance("peu importe"))


# ============================================================
# Routes
# ============================================================

@pytest.fixture
def api(monkeypatch):
    app = FastAPI()
    app.include_router(facture_ia.router, prefix="/api/v1")
    return TestClient(app)


def test_route_health(api):
    data = api.get("/api/v1/ia/facturation/health").json()

    assert data["success"] is True
    assert data["module"] == "M7"
    assert data["services"]["Agent M7 — RelanceGenerator"] is True


def test_route_calculer_montants(api):
    response = api.post("/api/v1/ia/facturation/calculer-montants", json={
        "type_client": "entreprise", "nb_participants": 20, "tarif_unitaire": 50_000,
    })

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["total_ht"] == 1_000_000.0
    assert data["remise_pct"] == 5.0            # >= 15 participants


def test_route_calculer_montants_type_invalide(api):
    response = api.post("/api/v1/ia/facturation/calculer-montants", json={
        "type_client": "particulier", "nb_participants": 1, "tarif_unitaire": 10,
    })

    assert response.status_code == 422


def test_route_generer_relance_404_si_facture_introuvable(api, monkeypatch):
    async def faux_fetch(facture_id):
        return None

    monkeypatch.setattr(facture_sync, "fetch_facture", faux_fetch)

    response = api.post("/api/v1/ia/facturation/relances/generer",
                        json={"facture_id": "inconnue"})

    assert response.status_code == 404


def test_route_generer_relance_200_avec_review(api, monkeypatch):
    async def faux_fetch(facture_id):
        return facture(date_echeance=date.today() - timedelta(days=20))

    monkeypatch.setattr(facture_sync, "fetch_facture", faux_fetch)
    facture_ia.get_facturation_orchestrator().relance_generator.llm = None

    response = api.post("/api/v1/ia/facturation/relances/generer",
                        json={"facture_id": "f-0001"})

    assert response.status_code == 200
    data = response.json()
    assert data["requires_human_action"] is True
    assert "En attente validation" in data["message"]


def test_le_router_de_l_application_monte_m7():
    """Garde-fou : mêmes bugs que router.py / analyse.py déjà vus deux fois."""
    from app.api.v1.router import api_router

    chemins = {route.path for route in api_router.routes}
    assert {
        "/ia/facturation/health",
        "/ia/facturation/calculer-montants",
        "/ia/facturation/relances/generer",
    } <= chemins
