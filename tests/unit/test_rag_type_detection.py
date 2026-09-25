# ============================================================
# TESTS — app/services/rag/type_detection_service.py (Étape E §2)
# ============================================================
# Aucun réseau réel : le LLM est désactivé par défaut (fixture autouse)
# pour tester le filtre Python et le repli par règles isolément ; un test
# dédié vérifie le chemin LLM avec un faux provider.
# ============================================================

import asyncio

import pytest

from app.services.llm import LLMNotAvailableError
from app.services.rag import type_detection_service as detection


def run(coro):
    return asyncio.run(coro)


@pytest.fixture(autouse=True)
def llm_indisponible(monkeypatch):
    def leve():
        raise LLMNotAvailableError("LLM coupé pour les tests")
    monkeypatch.setattr(detection, "get_llm_provider", leve)


# ---- Niveau 1 — filtre Python (conversationnel évident) ----

@pytest.mark.parametrize("message", [
    "bonjour", "Bonjour !", "salut", "bonsoir", "merci", "merci beaucoup",
    "au revoir", "à bientôt", "qui es-tu ?", "que sais-tu faire ?",
])
def test_filtre_conversationnel_evident_detecte(message):
    assert detection.filtre_conversationnel_evident(message) is True


@pytest.mark.parametrize("message", [
    "bonjour, c'est quoi le deep learning ?",  # exemple donné par la mission
    "quelles formations proposez-vous ?",
    "où est expliqué le surapprentissage ?",
])
def test_filtre_conversationnel_ne_capture_pas_les_vraies_questions(message):
    assert detection.filtre_conversationnel_evident(message) is False


def test_detecter_type_conversationnel_pur():
    assert run(detection.detecter_type("bonjour")) == "conversationnel"


def test_detecter_type_salutation_avec_question_n_est_pas_conversationnel():
    resultat = run(detection.detecter_type("bonjour, c'est quoi le deep learning ?"))
    assert resultat != "conversationnel"


# ---- Niveau 3 — repli par mots-clés (LLM indisponible ici) ----

def test_repli_catalogue():
    assert detection.detecter_type_regles("quelles formations proposez-vous ?") == "catalogue"


def test_repli_inventaire():
    assert detection.detecter_type_regles("combien de documents avez-vous indexés ?") == "inventaire"


def test_repli_localisation():
    assert detection.detecter_type_regles("où est expliqué le surapprentissage ?") == "localisation"


def test_repli_contenu_formation():
    assert detection.detecter_type_regles("donne moi le contenu de la formation IA") == "contenu_formation"


def test_repli_synthese_thematique():
    assert detection.detecter_type_regles("résumé des formations concernant la data") == "synthese_thematique"


def test_repli_aide_plateforme():
    assert detection.detecter_type_regles("comment valider une relance de facture ?") == "aide_plateforme"


def test_repli_defaut_question_fond():
    assert detection.detecter_type_regles("qu'est-ce que le surapprentissage ?") == "question_fond"


def test_detecter_type_utilise_le_repli_si_llm_indisponible():
    resultat = run(detection.detecter_type("quelles formations proposez-vous ?"))
    assert resultat == "catalogue"


# ---- Niveau 2 — LLM (faux provider, aucun réseau) ----

def test_detecter_type_via_llm(monkeypatch):
    class FauxLLM:
        async def generate_with_retry(self, **kwargs):
            return {"content": '{"type": "question_fond"}'}

    monkeypatch.setattr(detection, "get_llm_provider", lambda: FauxLLM())

    resultat = run(detection.detecter_type("qu'est-ce que le surapprentissage ?"))
    assert resultat == "question_fond"


def test_detecter_type_llm_reponse_invalide_utilise_le_repli(monkeypatch):
    class FauxLLM:
        async def generate_with_retry(self, **kwargs):
            return {"content": "ceci n'est pas du JSON"}

    monkeypatch.setattr(detection, "get_llm_provider", lambda: FauxLLM())

    resultat = run(detection.detecter_type("quelles formations proposez-vous ?"))
    assert resultat == "catalogue"  # repli par règles, pas de plantage


def test_detecter_type_llm_type_hors_liste_utilise_le_repli(monkeypatch):
    class FauxLLM:
        async def generate_with_retry(self, **kwargs):
            return {"content": '{"type": "type_invente"}'}

    monkeypatch.setattr(detection, "get_llm_provider", lambda: FauxLLM())

    resultat = run(detection.detecter_type("combien de documents avez-vous indexés ?"))
    assert resultat == "inventaire"
