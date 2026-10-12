# ============================================================
# TESTS — M2 TDR
# ============================================================
# Réécrit le 2026-09-24 : les 3 tests appelaient orchestrator.generer_tdr()
# (méthode synchrone avec validation intégrée) qui n'a jamais existé dans
# TdrOrchestrator depuis sa création (historique vérifié : ce fichier n'avait
# plus été modifié depuis le tout premier commit, alors que TdrOrchestrator
# a été réécrit 3 fois). La vraie méthode est generate() (async), qui ne
# valide pas les champs du brief et délègue tout à TDRService + le
# générateur de documents + la sync Backend. Tests réécrits pour couvrir le
# comportement RÉEL avec des doublures (aucun appel Groq/Backend/disque réel).
#
# MODIFIÉ le 2026-09-25 (correction 1b, mission "Étape 1") : generate() ne
# synchronise PLUS directement avec le Backend — un review HITL est créé,
# la sync n'a lieu qu'après approbation (voir tests/unit/test_tdr_hitl_sync.py
# pour la couverture complète de synchroniser_backend()). test_generate_success
# mettait à jour resultat["backend_sync"], qui n'existe plus : remplacé par
# une vérification du review HITL créé.
# ============================================================

import asyncio

import pytest

from app.orchestrator.tdr_orchestrator import TdrOrchestrator
from app.services.hitl import hitl_helper


def run(coro):
    return asyncio.run(coro)


@pytest.fixture(autouse=True)
def store_hitl_temporaire(monkeypatch, tmp_path):
    """Aucune review de test dans le vrai store data/hitl_reviews.json."""
    monkeypatch.setattr(hitl_helper, "STORAGE_PATH", tmp_path / "hitl_reviews.json")


class TestTdrOrchestrator:
    """Tests pour l'orchestrateur TDR (generate())."""

    def setup_method(self):
        self.orchestrator = TdrOrchestrator()

    def test_generate_success(self, monkeypatch):
        """Brief valide : TDR généré, documents créés, review HITL créé
        (PAS de sync Backend directe — correction 1b)."""
        brief = {
            "client": "Ministère de la Santé",
            "objectifs": "Former 50 agents à l'IA médicale",
            "public": "Agents de santé",
            "duree": "5 jours",
            "format": "Présentiel",
            "budget": "150 000 000 Ar",
        }

        async def faux_tdr_service_generate(b):
            return {"titre": "TDR Formation IA médicale", "sections": ["Contexte", "Objectifs"]}

        def faux_document_generator_generate(tdr_content, client):
            return ("tdr_test.docx", "tdr_test.pdf")

        monkeypatch.setattr(self.orchestrator.tdr_service, "generate", faux_tdr_service_generate)
        monkeypatch.setattr(self.orchestrator.document_generator, "generate", faux_document_generator_generate)

        resultat = run(self.orchestrator.generate(brief))

        assert resultat["success"] is True
        assert resultat["data"]["titre"] == "TDR Formation IA médicale"
        assert resultat["files"] == {"docx": "tdr_test.docx", "pdf": "tdr_test.pdf"}
        assert resultat["error"] is None

        assert resultat["_review_status"] == "pending_review"
        review = hitl_helper.get_review(resultat["_review_id"])
        assert review["agent_id"] == "agent_m2_tdr"
        assert review["status"] == "pending_review"

    def test_generate_service_indisponible(self):
        """TDRService non initialisé (ex. clé LLM absente) : RuntimeError explicite.

        _check_services() est appelé AVANT le bloc try/except de generate() :
        ce cas n'est donc pas transformé en {success: False}, il remonte tel quel.
        """
        self.orchestrator.tdr_service = None

        with pytest.raises(RuntimeError, match="TDRService"):
            run(self.orchestrator.generate({"client": "Client"}))

    def test_generate_reponse_llm_vide(self, monkeypatch):
        """TDRService renvoie None (LLM en échec/JSON irréparable) : échec propre, pas de crash."""
        async def faux_tdr_service_generate(b):
            return None

        monkeypatch.setattr(self.orchestrator.tdr_service, "generate", faux_tdr_service_generate)

        resultat = run(self.orchestrator.generate({"client": "Client"}))

        assert resultat["success"] is False
        assert "vide" in resultat["error"].lower()
