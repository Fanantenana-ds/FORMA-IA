# ============================================================
# TESTS — Validation des 3 corrections RAG (nov. 2026)
# ============================================================
# Correction 1 : vitesse — _suggestions() est statique (plus de LLM)
# Correction 2 : "REFAIRE" reconnu correctement (pas incompréhensible)
# Correction 3 : erreurs inattendues capturées (plus de HTTP 500 brut)
# ============================================================

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.llm import LLMNotAvailableError
from app.services.rag import type_detection_service as detection
from app.orchestrator.chat_orchestrator import ChatOrchestrator


def run(coro):
    return asyncio.run(coro)


# ═══════════════════════════════════════════════════════════
# CORRECTION 1 — Suggestions statiques (aucun appel LLM)
# ═══════════════════════════════════════════════════════════

class TestSuggestionsStatiques:
    """_suggestions() ne doit jamais appeler le LLM."""

    def test_suggestions_question_fond_retourne_liste(self):
        result = ChatOrchestrator._suggestions("question_fond")
        assert isinstance(result, list)
        assert len(result) >= 1

    def test_suggestions_catalogue(self):
        result = ChatOrchestrator._suggestions("catalogue")
        assert isinstance(result, list)

    def test_suggestions_incomprehensible(self):
        result = ChatOrchestrator._suggestions("incomprehensible")
        assert isinstance(result, list)

    def test_suggestions_avec_session_et_sources(self):
        """Avec une session, les suggestions ciblent les modules."""
        sources = [{"fichier": "cours_python.pdf", "formation": "Python", "page": 1, "score": 0.9}]
        with patch("app.orchestrator.chat_orchestrator.registre") as mock_reg:
            # Pas de modules indexés → repli sur les fichiers sources
            mock_reg.entrees_pour_session.return_value = []
            result = ChatOrchestrator._suggestions(
                "question_fond", session_id="sess-1", sources=sources
            )
            assert isinstance(result, list)

    def test_suggestions_dynamiques_existe_mais_non_appele_dans_traiter_message(self):
        """_suggestions_dynamiques existe encore mais n'est PAS appelé dans traiter_message."""
        import inspect
        source = inspect.getsource(ChatOrchestrator.traiter_message)
        assert "_suggestions_dynamiques" not in source, (
            "_suggestions_dynamiques ne doit plus être appelé dans traiter_message"
        )


# ═══════════════════════════════════════════════════════════
# CORRECTION 2 — "REFAIRE" reconnu, pas incompréhensible
# ═══════════════════════════════════════════════════════════

class TestRefaireReconnu:
    """Les mots de relance ne doivent pas être classés incompréhensibles."""

    @pytest.mark.parametrize("message", [
        "refaire", "REFAIRE", "Refaire",
        "retry", "RETRY",
        "encore", "suite",
        "recommence", "reessai",
        "continuer", "again",
    ])
    def test_pas_inintelligible(self, message):
        assert detection._est_inintelligible(message) is False, (
            f"'{message}' ne doit PAS être classé inintelligible"
        )

    @pytest.mark.parametrize("message", [
        "refaire", "retry", "encore", "suite", "recommence",
    ])
    def test_est_relance_contextuelle(self, message):
        assert detection._est_relance_contextuelle(message) is True, (
            f"'{message}' doit être reconnu comme relance contextuelle"
        )

    @pytest.fixture
    def llm_off(self, monkeypatch):
        def leve():
            raise LLMNotAvailableError("LLM coupé pour les tests")
        monkeypatch.setattr(detection, "get_llm_provider", leve)

    def test_refaire_sans_historique_donne_question_fond_ou_conversationnel(self, llm_off):
        """Sans contexte, 'refaire' ne doit pas retourner incompréhensible."""
        result = run(detection.detecter_type("refaire"))
        assert result != "incomprehensible", (
            f"'refaire' sans contexte retourné '{result}' — attendu: pas incomprehensible"
        )

    def test_refaire_avec_contexte_question_fond_reste_question_fond(self, llm_off):
        """Avec un contexte question_fond précédent, 'refaire' doit rester question_fond."""
        echange_precedent = SimpleNamespace(
            role="assistant",
            texte="Voici la réponse...",
            type_reponse="question_fond",
            session_id=None,
            module=None,
        )
        conv = SimpleNamespace(echanges=[echange_precedent])
        result = run(detection.detecter_type("refaire", conv=conv))
        assert result == "question_fond", (
            f"'refaire' avec contexte question_fond devrait retourner question_fond, got '{result}'"
        )

    def test_orchestrateur_rejoue_derniere_question_sur_relance(self):
        """L'orchestrateur doit rejouer la dernière vraie question sur une relance."""
        import inspect
        source = inspect.getsource(ChatOrchestrator.traiter_message)
        assert "_MOTS_RELANCE" in source, "Le bloc de relance doit définir _MOTS_RELANCE"
        assert "est_relance" in source, "Le bloc de relance doit calculer est_relance"
        assert "_e.texte" in source, "La relance doit récupérer le texte du dernier échange"


# ═══════════════════════════════════════════════════════════
# CORRECTION 3 — Plus de HTTP 500 brut sur erreur inattendue
# ═══════════════════════════════════════════════════════════

class TestPlusDeHTTP500:
    """Les exceptions inattendues doivent être capturées avec un message poli."""

    def test_except_exception_presente_dans_traiter_message(self):
        """Vérifier que le catch 'except Exception' existe dans traiter_message."""
        import inspect
        source = inspect.getsource(ChatOrchestrator.traiter_message)
        assert "except Exception as exc" in source, (
            "Un catch Exception global doit exister dans traiter_message"
        )
        assert "erreur est survenue" in source.lower() or "erreur inattendue" in source.lower(), (
            "Le message d'erreur poli doit être présent"
        )
        assert 'statut = "erreur"' in source, (
            "Le statut 'erreur' doit être défini dans le catch Exception"
        )

    @pytest.mark.asyncio
    async def test_erreur_inattendue_ne_leve_pas_exception(self):
        """L'orchestrateur doit absorber toute exception et retourner une réponse propre."""
        orch = ChatOrchestrator()

        # Simuler une conversation et registre vides
        with patch("app.orchestrator.chat_orchestrator.memoire") as mock_mem, \
             patch("app.orchestrator.chat_orchestrator.registre") as mock_reg, \
             patch("app.orchestrator.chat_orchestrator.detecter_type") as mock_detect:

            mock_mem.charger_conversation.return_value = SimpleNamespace(
                echanges=[], derniere_formation_code=None, user_id=None,
            )
            mock_mem.contexte_pour_session.return_value = SimpleNamespace(
                echanges=[], derniere_formation_code=None,
            )
            mock_mem.nouveau_id.return_value = "conv-test-123"
            mock_mem.ajouter_echange.return_value = SimpleNamespace(
                echanges=[], derniere_formation_code=None, user_id=None,
            )
            mock_mem.sauvegarder_conversation.return_value = None
            mock_reg.entrees_pour_session.return_value = []

            # La détection retourne question_fond mais le handler lève une exception
            mock_detect.return_value = "question_fond"

            with patch.object(orch, "_repondre_question_fond", side_effect=RuntimeError("💥 Erreur test")):
                with patch("app.orchestrator.chat_orchestrator.journal") as mock_journal:
                    mock_journal.enregistrer.return_value = None

                    result = await orch.traiter_message(
                        "Explique le deep learning",
                        conversation_id="conv-test-123",
                        session_id="sess-test",
                    )

        # Ne doit pas lever une exception
        assert result is not None
        assert "reponse" in result
        # La réponse doit être le message d'erreur poli
        assert "erreur" in result["reponse"].lower()
        # Les sources doivent être vides
        assert result.get("sources") == [] or result.get("sources") is None


# ═══════════════════════════════════════════════════════════
# TESTS COMPLÉMENTAIRES — Mots inintelligibles vrais
# ═══════════════════════════════════════════════════════════

class TestInintelligibles:
    """Vérifie que les VRAIS mots inintelligibles restent détectés."""

    @pytest.mark.parametrize("message", [
        "azerty", "kjhgf", "qsd", "xzc",
    ])
    def test_vrai_inintelligible(self, message):
        assert detection._est_inintelligible(message) is True, (
            f"'{message}' devrait être classé inintelligible"
        )

    @pytest.mark.parametrize("message", [
        "bonjour", "merci", "ok", "oui", "non",
        "aide", "help", "refaire", "encore", "suite",
        "rag", "tdr", "llm", "ia",
    ])
    def test_mots_connus_pas_inintelligibles(self, message):
        assert detection._est_inintelligible(message) is False, (
            f"'{message}' ne devrait PAS être classé inintelligible"
        )
