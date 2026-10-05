"""
Tests — GoogleFormsPublisherService + route /publish-forms

Deux niveaux de tests :
  1. Tests unitaires (sans appel Google) — vérifient la logique interne
  2. Test d'intégration RÉEL (appel Google Forms API)
     → marqué @pytest.mark.integration, sauté si GOOGLE_REFRESH_TOKEN absent

Pour lancer les tests d'intégration :
    pytest tests/unit/test_google_forms_publisher.py -v -m integration
"""

import asyncio
import os
import pytest

from unittest.mock import AsyncMock, MagicMock, patch

# ──────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────

def run(coro):
    return asyncio.run(coro)


FORMS_DATA_MINIMAL = {
    "inscription": {
        "title": "Fiche d'inscription TEST",
        "questions": [
            {"id": "ins_01", "label": "Votre nom", "type": "text", "required": True},
            {"id": "ins_02", "label": "Votre email", "type": "text", "required": True},
        ],
    },
    "test_avant": {
        "title": "Test AVANT TEST",
        "questions": [
            {
                "id": "av_01",
                "label": "Python est un langage :",
                "type": "multiple",
                "options": ["A. Compilé", "B. Interprété", "C. Les deux", "D. Aucun"],
                "correct_answer": "B",
                "required": True,
            },
        ],
    },
    "test_apres": {
        "title": "Test APRÈS TEST",
        "questions": [
            {
                "id": "ap_01",
                "label": "Python est un langage :",
                "type": "multiple",
                "options": ["A. Compilé", "B. Interprété", "C. Les deux", "D. Aucun"],
                "correct_answer": "B",
                "required": True,
            },
        ],
    },
    "satisfaction": {
        "title": "Satisfaction TEST",
        "questions": [
            {
                "id": "sat_01",
                "label": "Comment évaluez-vous la formation ?",
                "type": "scale",
                "required": True,
            },
            {
                "id": "sat_02",
                "label": "Commentaires libres",
                "type": "textarea",
                "required": False,
            },
        ],
    },
}


# ──────────────────────────────────────────────
# Tests unitaires — sans appel Google
# ──────────────────────────────────────────────

class TestIsAvailable:
    def test_indisponible_si_token_absent(self, monkeypatch):
        monkeypatch.delenv("GOOGLE_REFRESH_TOKEN", raising=False)
        from app.services.formations.google_forms_publisher_service import (
            GoogleFormsPublisherService,
        )
        assert GoogleFormsPublisherService.is_available() is False

    def test_disponible_si_token_present(self, monkeypatch):
        monkeypatch.setenv("GOOGLE_REFRESH_TOKEN", "fake-token")
        from app.services.formations.google_forms_publisher_service import (
            GoogleFormsPublisherService,
        )
        assert GoogleFormsPublisherService.is_available() is True


class TestBuildBatchRequests:
    """Vérifie la conversion des questions FORMA-IA → requêtes Google Forms."""

    @pytest.fixture
    def publisher(self, monkeypatch):
        monkeypatch.setenv("GOOGLE_REFRESH_TOKEN", "fake")
        monkeypatch.setenv("GOOGLE_OAUTH_CLIENT_PATH", "inexistant.json")
        from app.services.formations.google_forms_publisher_service import (
            GoogleFormsPublisherService,
        )
        svc = GoogleFormsPublisherService.__new__(GoogleFormsPublisherService)
        svc._forms_service = None
        svc._drive_service = None
        return svc

    def test_question_texte(self, publisher):
        questions = [{"label": "Ton nom", "type": "text", "required": True}]
        requests = publisher._build_batch_requests(questions, "inscription")
        assert len(requests) == 1
        item = requests[0]["createItem"]["item"]
        assert item["title"] == "Ton nom"
        assert "textQuestion" in item["questionItem"]["question"]

    def test_question_qcm(self, publisher):
        questions = [{
            "label": "Choix",
            "type": "multiple",
            "options": ["A. Option 1", "B. Option 2"],
            "required": True,
        }]
        requests = publisher._build_batch_requests(questions, "test_avant")
        item = requests[0]["createItem"]["item"]
        q = item["questionItem"]["question"]
        assert "choiceQuestion" in q
        assert q["choiceQuestion"]["type"] == "RADIO"
        assert len(q["choiceQuestion"]["options"]) == 2

    def test_question_scale(self, publisher):
        questions = [{"label": "Satisfaction", "type": "scale", "required": True}]
        requests = publisher._build_batch_requests(questions, "satisfaction")
        q = requests[0]["createItem"]["item"]["questionItem"]["question"]
        assert "scaleQuestion" in q
        assert q["scaleQuestion"]["low"] == 1
        assert q["scaleQuestion"]["high"] == 5

    def test_question_textarea(self, publisher):
        questions = [{"label": "Commentaires", "type": "textarea", "required": False}]
        requests = publisher._build_batch_requests(questions, "satisfaction")
        q = requests[0]["createItem"]["item"]["questionItem"]["question"]
        assert "textQuestion" in q
        assert q["textQuestion"]["paragraph"] is True

    def test_questions_vides(self, publisher):
        assert publisher._build_batch_requests([], "inscription") == []

    def test_index_correspond_a_lordre(self, publisher):
        questions = [
            {"label": "Q1", "type": "text"},
            {"label": "Q2", "type": "text"},
            {"label": "Q3", "type": "text"},
        ]
        requests = publisher._build_batch_requests(questions, "inscription")
        for i, req in enumerate(requests):
            assert req["createItem"]["location"]["index"] == i


# ──────────────────────────────────────────────
# Tests d'intégration — APPELS GOOGLE RÉELS
# ──────────────────────────────────────────────

INTEGRATION = pytest.mark.skipif(
    not os.getenv("GOOGLE_REFRESH_TOKEN"),
    reason="GOOGLE_REFRESH_TOKEN absent — test d'intégration ignoré",
)


@INTEGRATION
class TestIntegrationGoogleForms:
    """
    Tests d'intégration réels — créent de vrais formulaires Google Forms
    et les suppriment après chaque test.

    Ces tests nécessitent GOOGLE_REFRESH_TOKEN dans .env.
    """

    @pytest.fixture
    def publisher(self):
        from app.services.formations.google_forms_publisher_service import (
            GoogleFormsPublisherService,
        )
        return GoogleFormsPublisherService()

    def test_publisher_initialise_correctement(self, publisher):
        assert publisher._forms_service is not None
        assert publisher._drive_service is not None

    def test_publish_one_inscription(self, publisher):
        """Crée un vrai formulaire d'inscription et le supprime."""
        url = run(publisher.publish_one(
            section_data=FORMS_DATA_MINIMAL["inscription"],
            titre="TEST INTÉGRATION — Inscription — à supprimer",
            section_type="inscription",
        ))
        assert url.startswith("https://docs.google.com/forms/d/")
        assert "viewform" in url

        # Extraire le form_id et supprimer
        form_id = url.split("/d/")[1].split("/")[0]
        deleted = publisher.delete_form(form_id)
        assert deleted is True

    def test_publish_all_4_formulaires(self, publisher):
        """Crée les 4 formulaires d'une session complète et les supprime."""
        results = run(publisher.publish_all(
            forms_data=FORMS_DATA_MINIMAL,
            session_titre="TEST INTÉGRATION — à supprimer",
        ))

        # Vérifier les 4 sections
        assert "inscription" in results
        assert "test_avant" in results
        assert "test_apres" in results
        assert "satisfaction" in results

        # Vérifier que chaque URL est valide
        for section, url in results.items():
            assert url.startswith("https://docs.google.com/forms/d/"), \
                f"URL invalide pour {section}: {url}"

        # Supprimer tous les formulaires créés
        for section, url in results.items():
            form_id = url.split("/d/")[1].split("/")[0]
            publisher.delete_form(form_id)

    def test_publish_one_qcm(self, publisher):
        """Vérifie que les questions QCM sont créées correctement."""
        url = run(publisher.publish_one(
            section_data=FORMS_DATA_MINIMAL["test_avant"],
            titre="TEST INTÉGRATION — QCM — à supprimer",
            section_type="test_avant",
        ))
        assert url.startswith("https://docs.google.com/forms/d/")

        form_id = url.split("/d/")[1].split("/")[0]
        publisher.delete_form(form_id)


# ──────────────────────────────────────────────
# Test de la route HTTP /publish-forms
# ──────────────────────────────────────────────

class TestRoutePublishForms:
    """Tests sur la route POST /ia/formations/reviews/{id}/publish-forms."""

    @pytest.fixture
    def client(self, db_isolee):
        from app.main import app
        from fastapi.testclient import TestClient
        return TestClient(app)

    def test_review_inexistante_retourne_404(self, client):
        resp = client.post(
            "/api/v1/ia/formations/reviews/review-inexistant/publish-forms",
            json={"session_titre": "Test"},
            headers={"Authorization": "Bearer test"},
        )
        assert resp.status_code == 404

    def test_review_non_approuvee_retourne_422(self, client, monkeypatch):
        import app.api.v1.endpoints.formation_ia as mod
        monkeypatch.setattr(
            mod, "_get",
            lambda review_id: {
                "review_id": review_id,
                "agent_id": "agent_1_forms",
                "status": "pending_review",
                "data": {},
            },
        )
        resp = client.post(
            "/api/v1/ia/formations/reviews/review-test/publish-forms",
            json={"session_titre": "Test"},
            headers={"Authorization": "Bearer test"},
        )
        assert resp.status_code == 422
        assert "non approuvée" in resp.json()["detail"]

    def test_mauvais_agent_retourne_422(self, client, monkeypatch):
        import app.api.v1.endpoints.formation_ia as mod
        monkeypatch.setattr(
            mod, "_get",
            lambda review_id: {
                "review_id": review_id,
                "agent_id": "agent_m2_tdr",
                "status": "approved",
                "data": {},
            },
        )
        resp = client.post(
            "/api/v1/ia/formations/reviews/review-test/publish-forms",
            json={"session_titre": "Test"},
            headers={"Authorization": "Bearer test"},
        )
        assert resp.status_code == 422

    def test_token_absent_retourne_503(self, client, monkeypatch):
        import app.api.v1.endpoints.formation_ia as mod
        from app.services.formations import google_forms_publisher_service as pub_mod
        monkeypatch.setattr(
            mod, "_get",
            lambda review_id: {
                "review_id": review_id,
                "agent_id": "agent_1_forms",
                "status": "approved",
                "data": FORMS_DATA_MINIMAL,
            },
        )
        monkeypatch.delenv("GOOGLE_REFRESH_TOKEN", raising=False)
        resp = client.post(
            "/api/v1/ia/formations/reviews/review-test/publish-forms",
            json={"session_titre": "Test"},
            headers={"Authorization": "Bearer test"},
        )
        assert resp.status_code == 503
        assert "GOOGLE_REFRESH_TOKEN" in resp.json()["detail"]
