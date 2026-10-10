"""
Tests M4 — Assistance RH (bonus).

5 agents : présélection CV, CR entretien, email RH, contrat formateur,
           évaluation formateur post-session.

Aucun appel réseau : faux LLM, store HITL temporaire.

Exécution :
    python -m pytest tests/unit/test_m4_rh.py -q
"""

import asyncio
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.v1.endpoints import rh_ia
from app.orchestrator.rh_orchestrator import RhOrchestrator
from app.services.hitl import hitl_helper


def run(coro):
    return asyncio.run(coro)


@pytest.fixture(autouse=True)
def store_hitl_temporaire(monkeypatch, tmp_path):
    monkeypatch.setattr(hitl_helper, "STORAGE_PATH", tmp_path / "hitl_m4.json")


class FauxLLM:
    """Faux LLMProvider."""

    def __init__(self, contenu=None, erreur=None):
        self.contenu = contenu
        self.erreur = erreur
        self.appels = 0

    async def generate(self, system_prompt, user_prompt, temperature=0.3,
                       max_tokens=4000, json_mode=True):
        self.appels += 1
        if self.erreur:
            raise self.erreur
        import json
        c = self.contenu if isinstance(self.contenu, str) else json.dumps(self.contenu)
        return {"content": c, "finish_reason": "stop", "usage": {}, "model": "faux", "provider": "faux"}


@pytest.fixture
def api(monkeypatch, tmp_path):
    monkeypatch.setattr(hitl_helper, "STORAGE_PATH", tmp_path / "hitl_api.json")
    import app.orchestrator.rh_orchestrator as orch_mod
    monkeypatch.setattr(orch_mod, "_rh_orchestrator_instance", None)
    app = FastAPI()
    app.include_router(rh_ia.router, prefix="/api/v1")
    return TestClient(app)


# ============================================================
# Garde-fou — router
# ============================================================

def test_le_router_monte_m4():
    from app.api.v1.router import api_router
    chemins = {route.path for route in api_router.routes}
    assert {
        "/ia/rh/health",
        "/ia/rh/preselection",
        "/ia/rh/entretien/compte-rendu",
        "/ia/rh/email/brouillon",
        "/ia/rh/contrat-formateur",
        "/ia/rh/formateur/evaluer",
    } <= chemins


# ============================================================
# A1 — Présélection CV
# ============================================================

def test_preselection_fallback_sans_llm(monkeypatch):
    from app.services.rh.cv_preselecteur_service import CvPreselecteurService
    import app.services.rh.cv_preselecteur_service as mod
    monkeypatch.setattr(mod, "get_llm_provider", lambda: (_ for _ in ()).throw(Exception("hors ligne")))

    svc = CvPreselecteurService()
    result = run(svc.generate(
        cv_texte="Jean Dupont, formateur Python depuis 5 ans, diplômé ENI.",
        criteres_poste={"domaine": "Python", "competences": ["Python"], "niveau": "expert"},
    ))
    assert result["success"] is True
    assert result["decision"] in ("RETENU", "À_DISCUTER", "NON_RETENU")
    assert "_review_id" in result
    assert result["_review_status"] == "pending_review"


def test_preselection_avec_llm(monkeypatch):
    from app.services.rh.cv_preselecteur_service import CvPreselecteurService
    import app.services.rh.cv_preselecteur_service as mod
    import json

    contenu = {
        "nom_candidat": "Rakoto Jean",
        "poste_vise": "Python",
        "score_global": 82,
        "decision": "RETENU",
        "points_forts": ["Expérimenté", "Pédagogue"],
        "reserves": [],
        "questions_entretien": ["Q1", "Q2", "Q3"],
        "adequation_domaine": {"score": 85, "justification": "Expert Python"},
        "experience_formation": {"annees_estimees": 5, "types": ["pro"], "justification": "ok"},
        "competences_techniques": [{"competence": "Python", "niveau_estime": "expert"}],
        "synthese": "Excellent profil.",
    }
    faux = FauxLLM(contenu=contenu)
    monkeypatch.setattr(mod, "get_llm_provider", lambda: faux)

    svc = CvPreselecteurService()
    result = run(svc.generate(
        cv_texte="Rakoto Jean — formateur Python expert.",
        criteres_poste={"domaine": "Python", "competences": ["Python"]},
    ))
    assert result["decision"] == "RETENU"
    assert result["score_global"] == 82
    assert faux.appels == 1


# ============================================================
# A2 — Compte-rendu entretien
# ============================================================

def test_entretien_fallback_sans_llm(monkeypatch):
    from app.services.rh.entretien_service import EntretienService
    import app.services.rh.entretien_service as mod
    monkeypatch.setattr(mod, "get_llm_provider", lambda: (_ for _ in ()).throw(Exception("hors ligne")))

    svc = EntretienService()
    result = run(svc.generate(
        notes_brutes="Candidat ponctuel, bonne présentation, maîtrise Python.",
        candidat="Rabe Marie",
        poste="Formatrice Python",
    ))
    assert result["success"] is True
    assert result["decision"] in ("RECRUTER", "APPROFONDIR", "NE_PAS_RECRUTER")
    assert "_review_id" in result


# ============================================================
# A3 — Email RH
# ============================================================

def test_email_type_invalide():
    from app.services.rh.email_rh_service import EmailRhService
    svc = EmailRhService()
    with pytest.raises(ValueError, match="type_email invalide"):
        run(svc.generate(type_email="INCONNU", destinataire="Test"))


def test_email_fallback_acceptation(monkeypatch):
    from app.services.rh.email_rh_service import EmailRhService
    import app.services.rh.email_rh_service as mod
    monkeypatch.setattr(mod, "get_llm_provider", lambda: (_ for _ in ()).throw(Exception("hors ligne")))

    svc = EmailRhService()
    result = run(svc.generate(type_email="ACCEPTATION", destinataire="Rabe Marie"))
    assert result["success"] is True
    assert result["type_email"] == "ACCEPTATION"
    assert "objet" in result
    assert "corps" in result
    assert "_review_id" in result


def test_email_fallback_refus(monkeypatch):
    from app.services.rh.email_rh_service import EmailRhService
    import app.services.rh.email_rh_service as mod
    monkeypatch.setattr(mod, "get_llm_provider", lambda: (_ for _ in ()).throw(Exception("hors ligne")))

    svc = EmailRhService()
    result = run(svc.generate(type_email="REFUS", destinataire="Rakoto Jean"))
    assert result["type_email"] == "REFUS"
    assert "corps" in result


# ============================================================
# A4 — Contrat formateur
# ============================================================

FORMATEUR_TEST = {
    "nom": "M. Rabe Hery",
    "adresse": "Antananarivo",
    "telephone": "+261 34 00 000 00",
    "email": "rabe@example.com",
    "tarif_journalier": 500_000,
}
SESSION_TEST = {
    "titre": "Formation Python IA",
    "dates": ["2026-10-05", "2026-10-06"],
    "nb_jours": 2,
    "lieu": "Antananarivo",
    "nb_participants": 20,
    "description": "Formation Python niveau avancé.",
}


def test_contrat_formateur_fallback(monkeypatch):
    from app.services.rh.contrat_formateur_service import ContratFormateurService
    import app.services.rh.contrat_formateur_service as mod
    monkeypatch.setattr(mod, "get_llm_provider", lambda: (_ for _ in ()).throw(Exception("hors ligne")))

    svc = ContratFormateurService()
    result = run(svc.generate(formateur=FORMATEUR_TEST, session=SESSION_TEST))

    assert result["success"] is True
    assert result["remuneration"]["total_brut"] == 1_000_000
    assert "texte_complet" in result
    assert "ALT-CONT-FORM" in result["reference_contrat"]
    assert "_review_id" in result


def test_contrat_formateur_total_calcule(monkeypatch):
    from app.services.rh.contrat_formateur_service import ContratFormateurService
    import app.services.rh.contrat_formateur_service as mod
    monkeypatch.setattr(mod, "get_llm_provider", lambda: (_ for _ in ()).throw(Exception("hors ligne")))

    svc = ContratFormateurService()
    f = {**FORMATEUR_TEST, "tarif_journalier": 300_000}
    s = {**SESSION_TEST, "nb_jours": 3}
    result = run(svc.generate(formateur=f, session=s))
    assert result["remuneration"]["total_brut"] == 900_000


# ============================================================
# A5 — Évaluation formateur post-session
# ============================================================

def test_evaluation_fallback_score_calcule(monkeypatch):
    from app.services.rh.evaluation_formateur_service import EvaluationFormateurService
    import app.services.rh.evaluation_formateur_service as mod
    monkeypatch.setattr(mod, "get_llm_provider", lambda: (_ for _ in ()).throw(Exception("hors ligne")))

    svc = EvaluationFormateurService()
    result = run(svc.generate(
        formateur="M. Rabe Hery",
        session="Formation Python IA",
        donnees_session={
            "satisfaction": {
                "score_moyen": 4.5,
                "points_positifs": ["Clair"],
                "points_negatifs": [],
            },
            "presences": {"taux_moyen_pct": 92.0, "anomalies": False},
        },
    ))
    assert result["success"] is True
    assert result["score_global"] is not None
    assert result["recommandation"] in ("OUI", "CONDITIONNEL", "NON")
    assert "_review_id" in result
    assert result["_review_status"] == "pending_review"


def test_evaluation_recommandation_oui_si_bon_score(monkeypatch):
    from app.services.rh.evaluation_formateur_service import EvaluationFormateurService
    import app.services.rh.evaluation_formateur_service as mod
    monkeypatch.setattr(mod, "get_llm_provider", lambda: (_ for _ in ()).throw(Exception("hors ligne")))

    svc = EvaluationFormateurService()
    result = run(svc.generate(
        formateur="M. Rabe Hery",
        session="Formation Python IA",
        donnees_session={
            "satisfaction": {"score_moyen": 5.0, "points_positifs": ["Excellent"], "points_negatifs": []},
            "presences": {"taux_moyen_pct": 100.0, "anomalies": False},
        },
    ))
    assert result["recommandation"] == "OUI"


# ============================================================
# Orchestrateur — chaîne complète
# ============================================================

def test_orchestrateur_tous_agents_actifs():
    orch = RhOrchestrator()
    assert orch.preselection is not None
    assert orch.entretien is not None
    assert orch.email is not None
    assert orch.contrat is not None
    assert orch.evaluation is not None


def test_orchestrateur_preselection_fallback(monkeypatch):
    import app.services.rh.cv_preselecteur_service as mod
    monkeypatch.setattr(mod, "get_llm_provider", lambda: (_ for _ in ()).throw(Exception("hors ligne")))

    orch = RhOrchestrator()
    result = run(orch.preselectionner_cv(
        cv_texte="Formateur Python avec 3 ans d'expérience professionnelle.",
        criteres_poste={"domaine": "Python"},
    ))
    assert result["success"] is True
    assert "_review_id" in result


def test_orchestrateur_contrat_formateur(monkeypatch):
    import app.services.rh.contrat_formateur_service as mod
    monkeypatch.setattr(mod, "get_llm_provider", lambda: (_ for _ in ()).throw(Exception("hors ligne")))

    orch = RhOrchestrator()
    result = run(orch.generer_contrat_formateur(
        formateur=FORMATEUR_TEST,
        session=SESSION_TEST,
    ))
    assert result["success"] is True
    assert result["remuneration"]["total_brut"] == 1_000_000


# ============================================================
# Routes HTTP
# ============================================================

def test_route_health(api):
    r = api.get("/api/v1/ia/rh/health")
    assert r.status_code == 200
    assert r.json()["success"] is True


def test_route_preselection_422_si_cv_vide(api):
    r = api.post("/api/v1/ia/rh/preselection", json={
        "cv_texte": "x",  # trop court (min_length=50)
        "criteres_poste": {"domaine": "Python"},
    })
    assert r.status_code == 422


def test_route_email_type_invalide(api):
    r = api.post("/api/v1/ia/rh/email/brouillon", json={
        "type_email": "MAUVAIS",
        "destinataire": "Test",
    })
    assert r.status_code == 422


def test_route_contrat_200(api, monkeypatch):
    import app.services.rh.contrat_formateur_service as mod
    monkeypatch.setattr(mod, "get_llm_provider", lambda: (_ for _ in ()).throw(Exception("hors ligne")))

    r = api.post("/api/v1/ia/rh/contrat-formateur", json={
        "formateur": {
            "nom": "M. Rabe Hery",
            "tarif_journalier": 500000,
        },
        "session": {
            "titre": "Formation Python IA",
            "dates": ["2026-10-05"],
            "nb_jours": 1,
        },
    })
    assert r.status_code == 200
    data = r.json()
    assert data["success"] is True
    assert data["requires_human_action"] is True   # HITL contrat


def test_route_evaluer_200(api, monkeypatch):
    import app.services.rh.evaluation_formateur_service as mod
    monkeypatch.setattr(mod, "get_llm_provider", lambda: (_ for _ in ()).throw(Exception("hors ligne")))

    r = api.post("/api/v1/ia/rh/formateur/evaluer", json={
        "formateur": "M. Rabe Hery",
        "session": "Formation Python IA",
        "donnees_session": {
            "satisfaction": {
                "score_moyen": 4.2,
                "points_positifs": ["ok"],
                "points_negatifs": [],
            },
            "presences": {"taux_moyen_pct": 90.0, "anomalies": False},
        },
    })
    assert r.status_code == 200
    data = r.json()
    assert data["success"] is True
    assert data["requires_human_action"] is True   # HITL sur évaluation
