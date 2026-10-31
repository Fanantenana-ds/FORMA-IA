"""Tests isolés du routeur vocal.

Ils utilisent un fournisseur LLM factice : aucun appel Groq/Claude ni réseau.
"""

import asyncio
import json

import pytest

import app.services.vocal.routeur_vocal as vocal


def run(coro):
    return asyncio.run(coro)


class FauxLLM:
    def __init__(self, contenu: dict):
        self.contenu = contenu
        self.appel = None

    async def generate(self, **kwargs):
        self.appel = kwargs
        return {"content": json.dumps(self.contenu)}


def test_router_utilise_le_contrat_generate(monkeypatch):
    faux_llm = FauxLLM({
        "intention": "creer_seance",
        "confiance": 0.91,
        "parametres": {"nom_formation": "Python", "date": "2026-10-29"},
        "parametres_manquants": [],
        "reponse_vocale": "Je prépare la séance Python pour jeudi.",
        "action_frontend": "ouvrir_formulaire_seance",
        "prefill": {"nom_formation": "Python", "date": "2026-10-29"},
    })
    monkeypatch.setattr(vocal, "get_llm_provider", lambda: faux_llm)

    resultat = run(vocal.router_commande("Crée une séance Python pour jeudi"))

    assert resultat["intention"] == "creer_seance"
    assert resultat["action_frontend"] == "ouvrir_formulaire_seance"
    assert faux_llm.appel["json_mode"] is True
    assert faux_llm.appel["reasoning_effort"] == "low"
    assert "Crée une séance Python pour jeudi" in faux_llm.appel["user_prompt"]


def test_router_repond_honnetement_si_json_invalide(monkeypatch):
    class FauxLLMInvalide:
        async def generate(self, **kwargs):
            return {"content": "pas du json"}

    monkeypatch.setattr(vocal, "get_llm_provider", FauxLLMInvalide)

    resultat = run(vocal.router_commande("Prépare une demande complexe dont les paramètres ne sont pas connus"))

    assert resultat["intention"] == "hors_perimetre"
    assert resultat["confiance"] == 0.0
    assert resultat["action_frontend"] is None


def test_salutation_est_traitee_sans_llm(monkeypatch):
    def llm_interdit():
        raise AssertionError("Une salutation ne doit pas appeler le LLM")

    monkeypatch.setattr(vocal, "get_llm_provider", llm_interdit)

    resultat = run(vocal.router_commande("bonsoir"))

    assert resultat["intention"] == "conversationnel"
    assert resultat["confiance"] == 1.0


def test_question_plateforme_mal_transcrite_va_vers_c3_sans_llm(monkeypatch):
    def llm_interdit():
        raise AssertionError("L'aide plateforme doit être routée localement")

    monkeypatch.setattr(vocal, "get_llm_provider", llm_interdit)

    resultat = run(vocal.router_commande("comment utiliser cette platforme"))

    assert resultat["intention"] == "question_rag"
    assert resultat["action_frontend"] == "ouvrir_chat_rag"


@pytest.mark.parametrize("commande", [
    "faire la detetection de marche",
    "fais la détection de marché",
    "detection automatique du marche",
])
def test_variantes_orales_detection_marche_sont_locales(monkeypatch, commande):
    def llm_interdit():
        raise AssertionError("Une commande de veille non ambiguë ne doit pas consommer Groq")

    monkeypatch.setattr(vocal, "get_llm_provider", llm_interdit)
    resultat = run(vocal.router_commande(commande))
    assert resultat["intention"] == "veille_marche"
    assert resultat["action_frontend"] == "lancer_veille"


@pytest.mark.parametrize("champ,valeur", [
    ("intention", []), ("intention", "supprimer_base"),
    ("confiance", 2), ("confiance", float("nan")),
    ("parametres_manquants", [42]), ("prefill", "invalide"),
])
def test_contrat_llm_invalide_ne_declenche_aucune_action(monkeypatch, champ, valeur):
    contenu = {
        "intention": "creer_seance", "confiance": 0.9,
        "reponse_vocale": "Préparation", "action_frontend": "ouvrir_formulaire_seance",
        "prefill": {}, "parametres_manquants": [],
    }
    contenu[champ] = valeur
    monkeypatch.setattr(vocal, "get_llm_provider", lambda: FauxLLM(contenu))
    resultat = run(vocal.router_commande("Crée une séance"))
    assert resultat["action_frontend"] is None
    assert resultat["confiance"] == 0


def test_action_llm_est_remplacee_par_la_liste_blanche(monkeypatch):
    contenu = {
        "intention": "afficher_sessions", "confiance": 0.9,
        "reponse_vocale": "Sessions", "action_frontend": "supprimer_base",
        "prefill": {}, "parametres_manquants": [],
    }
    monkeypatch.setattr(vocal, "get_llm_provider", lambda: FauxLLM(contenu))
    assert run(vocal.router_commande("Ouvre les sessions"))["action_frontend"] == "afficher_sessions"


@pytest.mark.parametrize("question",["quelles ton roles","tu es creer pouauoi","Qui es-tu ?","Quel est ton rôle ?"])
def test_role_assistant_ne_depend_pas_du_llm(monkeypatch,question):
    def forbidden(): raise AssertionError("Pas de quota LLM pour la présentation")
    monkeypatch.setattr(vocal,"get_llm_provider",forbidden)
    result=asyncio.run(vocal.router_commande(question))
    assert result["intention"]=="conversationnel"
    assert "FORMA-IA" in result["reponse_vocale"]


def test_identite_explique_aussi_la_raison_metier_de_la_plateforme(monkeypatch):
    def forbidden():
        raise AssertionError("La présentation métier locale ne doit pas consommer Groq")

    monkeypatch.setattr(vocal, "get_llm_provider", forbidden)
    result = run(vocal.router_commande("Pourquoi cette plateforme a été créée ?"))
    assert result["intention"] == "conversationnel"
    assert "opportunité" in result["reponse_vocale"]
    assert "factur" in result["reponse_vocale"]
