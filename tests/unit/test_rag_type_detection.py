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


@pytest.mark.parametrize("message", [
    "DONNE MOI LA RESUME DE SUPPORT DU COURS ACTUELLEMENT",
    "résume les supports de cette session",
    "refaire le résumé de ces supports",
])
def test_repli_reconnait_demande_resume_support(message):
    assert detection.detecter_type_regles(message) == "contenu_formation"


def test_repli_aide_plateforme():
    assert detection.detecter_type_regles("comment valider une relance de facture ?") == "aide_plateforme"


def test_repli_defaut_question_fond():
    assert detection.detecter_type_regles("qu'est-ce que le surapprentissage ?") == "question_fond"


def test_detecter_type_utilise_le_repli_si_llm_indisponible():
    resultat = run(detection.detecter_type("quelles formations proposez-vous ?"))
    assert resultat == "catalogue"


@pytest.mark.parametrize(("message", "attendu"), [
    (
        "a partir de ces document creer moi des exercice que je peux poser oralement au participant de cette formations",
        "question_fond",
    ),
    ("je vous parle sur les support de cours que je veux indexer", "contenu_formation"),
])
def test_demande_claire_sur_supports_ne_devient_pas_incomprehensible(message, attendu, monkeypatch):
    async def classifier_incomprehensible(*_args, **_kwargs):
        return "incomprehensible"

    monkeypatch.setattr(detection, "_detecter_via_llm", classifier_incomprehensible)

    assert run(detection.detecter_type(message)) == attendu


def test_session_active_garde_une_demande_pedagogique_generale_dans_le_rag(monkeypatch):
    async def classifier_incomprehensible(*_args, **_kwargs):
        return "incomprehensible"

    monkeypatch.setattr(detection, "_detecter_via_llm", classifier_incomprehensible)
    message = "Propose une activité pour vérifier ce que les apprenants ont retenu."

    assert run(detection.detecter_type(message, session_id="session-ia")) == "question_fond"
    assert run(detection.detecter_type(message)) == "incomprehensible"


@pytest.mark.parametrize("mauvais_type", ["conversationnel", "hors_sujet", "catalogue", "inventaire"])
def test_session_active_recadre_une_question_documentaire_mal_classee(mauvais_type, monkeypatch):
    async def classifier_errone(*_args, **_kwargs):
        return mauvais_type

    monkeypatch.setattr(detection, "_detecter_via_llm", classifier_errone)
    message = "Bonjour chat, explique-moi la reconnaissance des objets du cours."

    assert run(detection.detecter_type(message, session_id="session-ia")) == "question_fond"


def test_salutation_pure_reste_conversationnelle_meme_avec_session():
    assert run(detection.detecter_type("bonjour", session_id="session-ia")) == "conversationnel"


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


# ---- Abréviations conversationnelles ----

@pytest.mark.parametrize("message", [
    "bjr", "bjr !", "Bjr", "bsr", "slt", "slut", "cc", "wesh", "hey",
    "mrc", "thks", "tchao", "ciao",
])
def test_abreviations_reconnues_comme_conversationnel(message):
    """Les abréviations de salutation/remerciement doivent être détectées
    par le filtre Python sans passer par le LLM."""
    assert detection.filtre_conversationnel_evident(message) is True


@pytest.mark.parametrize("message", [
    "bjr, c'est quoi le deep learning ?",
    "slt comment valider une facture ?",
    "slut, liste les formations disponibles",
])
def test_abreviation_salutation_avec_question_pas_conversationnel(message):
    """Abréviation de salutation SUIVIE d'une vraie question → pas conversationnel."""
    assert detection.filtre_conversationnel_evident(message) is False


# ---- Messages inintelligibles ----

@pytest.mark.parametrize("message", [
    "azerty", "qsdf", "lkjhg", "xwz", "zzzz",
    # "azerty formation" n'est pas inintelligible car "formation" est un vrai mot
    # → le LLM ou le repli par règles le gère comme question_fond
])
def test_est_inintelligible_frappe_aleatoire(message):
    assert detection._est_inintelligible(message) is True


@pytest.mark.parametrize("message", [
    "bjr",           # abréviation connue → pas inintelligible
    "slt",           # abréviation connue
    "rag",           # terme du domaine métier
    "tdr",           # terme du domaine métier
    "ia",            # terme du domaine métier
    "quelles formations proposez-vous ?",   # phrase normale
    "formation 2025",   # contient un chiffre
])
def test_pas_inintelligible_cas_legaux(message):
    assert detection._est_inintelligible(message) is False


def test_detecter_type_incomprehensible():
    """Un message de frappe aléatoire est classé incomprehensible sans appel LLM."""
    resultat = run(detection.detecter_type("qsdfgh"))
    assert resultat == "incomprehensible"


def test_detecter_type_incomprehensible_ne_devient_pas_question_fond():
    """Un message inintelligible ne doit pas déclencher la recherche vectorielle."""
    resultat = run(detection.detecter_type("lkjhg"))
    assert resultat == "incomprehensible"


# ---- Handler incomprehensible dans le chat orchestrator ----

def test_handler_incomprehensible_dans_orchestrateur():
    """Le chat orchestrateur retourne une réponse de clarification professionnelle."""
    import asyncio
    from app.orchestrator.chat_orchestrator import ChatOrchestrator

    class FauxRepo:
        def modeles_presents(self, collection=None): return []
        def rechercher_par_similarite(self, *a, **kw): return []

    orch = ChatOrchestrator(repository=FauxRepo())

    # Bypass detection → forcer le type directement
    reponse = orch._repondre_incomprehensible("qsdfgh")
    assert "reformuler" in reponse.lower() or "compris" in reponse.lower()
    # Pas de sources → pas d'hallucination
    assert isinstance(reponse, str)
    assert len(reponse) > 20
