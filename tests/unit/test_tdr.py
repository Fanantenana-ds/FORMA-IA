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
# ============================================================

import asyncio

import pytest

from app.orchestrator.tdr_orchestrator import TdrOrchestrator


def run(coro):
    return asyncio.run(coro)


class TestTdrOrchestrator:
    """Tests pour l'orchestrateur TDR (generate())."""

    def setup_method(self):
        self.orchestrator = TdrOrchestrator()

    def test_generate_success(self, monkeypatch):
        """Brief valide : TDR généré, documents créés, sync backend tentée."""
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

        async def faux_sync_tdr_to_backend(**kwargs):
            return {"success": True, "skipped": False}

        monkeypatch.setattr(self.orchestrator.tdr_service, "generate", faux_tdr_service_generate)
        monkeypatch.setattr(self.orchestrator.document_generator, "generate", faux_document_generator_generate)
        monkeypatch.setattr(
            "app.orchestrator.tdr_orchestrator.sync_tdr_to_backend",
            faux_sync_tdr_to_backend,
        )

        resultat = run(self.orchestrator.generate(brief))

        assert resultat["success"] is True
        assert resultat["data"]["titre"] == "TDR Formation IA médicale"
        assert resultat["files"] == {"docx": "tdr_test.docx", "pdf": "tdr_test.pdf"}
        assert resultat["backend_sync"]["success"] is True
        assert resultat["error"] is None

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
