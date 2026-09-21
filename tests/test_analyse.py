import pytest
from fastapi.testclient import TestClient

from app.database import get_db
from app.models.historique_analyse import HistoriqueAnalyse
from app.services.backend_sync import base_sync
from app.services.veille import opportunity_analysis_service as analyse_ia
from app.main import app

client = TestClient(app)

TOKEN = ""
AUTH_HEADERS = {"Authorization": f"Bearer {TOKEN}"}


# tests/test_analyse.py

def test_analyse_sans_auth(client):
    response = client.post(
        "/api/v1/opportunites/16c6314c-9c24-4654-abb9-2df429a49937/analyse"
    )
    assert response.status_code == 401


def test_analyse_opportunite_inexistante(client_authenticated):
    response = client_authenticated.post(
        "/api/v1/opportunites/00000000-9c24-4654-abb9-2df429a49937/analyse"
    )
    assert response.status_code == 404


def test_analyse_avec_auth_et_opportunite_existante(client_authenticated):
    # L'opportunité est créée par le test lui-même (avant : UUID codé en dur,
    # présent seulement dans la base d'un développeur). Elle est annulée à la
    # fin du test (fixture db_isolee).
    creation = client_authenticated.post(
        "/api/v1/opportunites",
        json={"source": "TEXTE", "contenu": "Appel d'offre formation IA"},
    )
    assert creation.status_code == 201
    opportunite_id = creation.json()["id"]

    response = client_authenticated.post(
        f"/api/v1/opportunites/{opportunite_id}/analyse"
    )
    assert response.status_code == 200
    data = response.json()
    assert "score_pertinence" in data

    relue = client_authenticated.get(f"/api/v1/opportunites/{opportunite_id}")
    assert relue.json()["statut"] == "ANALYSEE"

# ============================================================
# Scoring IA (M1) branché sur la route
# ============================================================

TEXTE_IA = (
    "Le Ministère de l'Économie à Antananarivo recherche un prestataire pour une "
    "formation IA et prompt engineering de 30 agents.\n"
    "Dossier complet disponible auprès du secrétariat de la direction générale."
)


@pytest.fixture(autouse=True)
def analyse_sans_backend(monkeypatch):
    """L'analyse ne doit jamais recréer l'opportunité dans le Backend (doublon)."""
    async def interdit(*args, **kwargs):
        raise AssertionError("L'analyse ne doit pas appeler le Backend")

    monkeypatch.setattr(base_sync, "backend_request", interdit)


def _creer_opportunite(client, contenu, **extra):
    creation = client.post(
        "/api/v1/opportunites", json={"source": "TEXTE", "contenu": contenu, **extra}
    )
    assert creation.status_code == 201
    return creation.json()["id"]


def _historiques(opportunite_id):
    """Lignes d'historique lues dans la même transaction (annulée en fin de test)."""
    generateur = app.dependency_overrides[get_db]()
    db = next(generateur)
    try:
        return db.query(HistoriqueAnalyse).filter(
            HistoriqueAnalyse.opportunite_id == opportunite_id
        ).all()
    finally:
        generateur.close()


def test_analyse_renvoie_un_score_reel_entre_0_et_1(client_authenticated):
    opportunite_id = _creer_opportunite(
        client_authenticated, TEXTE_IA, budget=60_000_000
    )

    response = client_authenticated.post(
        f"/api/v1/opportunites/{opportunite_id}/analyse"
    )

    assert response.status_code == 200
    data = response.json()
    assert 0.5 < data["score_pertinence"] <= 1.0      # avant : toujours 0.0
    assert data["domaine"] == "IA"
    assert data["budget"] == 60_000_000
    assert data["objet"].startswith("Le Ministère de l'Économie")


def test_analyse_persiste_le_score_sur_l_opportunite_et_dans_l_historique(
    client_authenticated,
):
    opportunite_id = _creer_opportunite(client_authenticated, TEXTE_IA)

    score = client_authenticated.post(
        f"/api/v1/opportunites/{opportunite_id}/analyse"
    ).json()["score_pertinence"]

    relue = client_authenticated.get(f"/api/v1/opportunites/{opportunite_id}").json()
    assert relue["score_pertinence"] == score
    assert relue["statut"] == "ANALYSEE"

    historique = _historiques(opportunite_id)
    assert len(historique) == 1
    assert historique[0].score_pertinence == score


def test_analyse_ne_modifie_pas_les_champs_saisis_par_l_utilisateur(
    client_authenticated,
):
    opportunite_id = _creer_opportunite(client_authenticated, TEXTE_IA)

    client_authenticated.post(f"/api/v1/opportunites/{opportunite_id}/analyse")

    relue = client_authenticated.get(f"/api/v1/opportunites/{opportunite_id}").json()
    assert relue["objet"] is None          # le résultat va dans l'historique
    assert relue["domaine"] is None
    assert relue["budget"] is None


def test_analyse_distingue_un_contenu_pertinent_d_un_contenu_hors_sujet(
    client_authenticated,
):
    pertinent = _creer_opportunite(client_authenticated, TEXTE_IA)
    hors_sujet = _creer_opportunite(
        client_authenticated, "Formation Excel et Word pour le personnel"
    )

    score_pertinent = client_authenticated.post(
        f"/api/v1/opportunites/{pertinent}/analyse"
    ).json()["score_pertinence"]
    score_hors_sujet = client_authenticated.post(
        f"/api/v1/opportunites/{hors_sujet}/analyse"
    ).json()["score_pertinence"]

    assert score_pertinent > score_hors_sujet


def test_analyse_le_domaine_saisi_est_respecte(client_authenticated):
    opportunite_id = _creer_opportunite(client_authenticated, TEXTE_IA, domaine="DATA")

    data = client_authenticated.post(
        f"/api/v1/opportunites/{opportunite_id}/analyse"
    ).json()

    assert data["domaine"] == "DATA"


def test_analyse_avec_extraction_llm_completee_par_le_faux_llm(
    client_authenticated, monkeypatch
):
    class FauxLLM:
        async def analyze(self, query, results):
            return {"opportunities": [{
                "title": "Formation IA — Ministère",
                "budget": "60M Ar",
                "deadline": "2026-12-15",
                "organizer": "Ministère de l'Économie",
            }]}

    monkeypatch.setenv("ANALYSE_USE_LLM", "true")
    monkeypatch.setattr(analyse_ia, "_creer_llm_service", lambda: FauxLLM())
    opportunite_id = _creer_opportunite(client_authenticated, TEXTE_IA)

    response = client_authenticated.post(
        f"/api/v1/opportunites/{opportunite_id}/analyse"
    )

    assert response.status_code == 200
    data = response.json()
    assert data["objet"] == "Formation IA — Ministère"
    assert data["budget"] == 60_000_000
    assert data["echeance"].startswith("2026-12-15")
    assert data["score_pertinence"] > 0.5


def test_analyse_ne_plante_pas_si_le_llm_est_en_panne(client_authenticated, monkeypatch):
    class LLMEnPanne:
        async def analyze(self, query, results):
            raise RuntimeError("Groq indisponible")

    monkeypatch.setenv("ANALYSE_USE_LLM", "true")
    monkeypatch.setattr(analyse_ia, "_creer_llm_service", lambda: LLMEnPanne())
    opportunite_id = _creer_opportunite(client_authenticated, TEXTE_IA)

    response = client_authenticated.post(
        f"/api/v1/opportunites/{opportunite_id}/analyse"
    )

    assert response.status_code == 200
    assert response.json()["score_pertinence"] > 0.0
