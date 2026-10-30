"""Agent de routage vocal FORMA-IA.

Reçoit une commande texte (issue de la reconnaissance vocale),
détecte l'intention, extrait les paramètres et retourne l'action
à exécuter sur le frontend ainsi que la réponse vocale.
"""

import json
import logging
import re
import unicodedata
from datetime import datetime
from zoneinfo import ZoneInfo
from pathlib import Path

import yaml

from app.services.llm.llm_factory import get_llm_provider
from app.services.llm.llm_provider import LLMError

logger = logging.getLogger(__name__)

_PROMPT_PATH = Path(__file__).parent.parent.parent / "prompts" / "vocal" / "routeur.yaml"


def _reponse_locale(commande: str) -> dict | None:
    """Gère les demandes sans ambiguïté sans consommer de quota LLM."""
    texte = " ".join(commande.lower().strip().split())
    simple = "".join(char for char in unicodedata.normalize("NFD", texte) if not unicodedata.combining(char))
    simple = " ".join(re.sub(r"[^a-z0-9 ]", " ", simple).split())
    identities = {"qui es tu", "quel est ton role", "quels sont tes roles", "quelles sont tes roles", "quelles ton roles", "ton role", "tes roles", "a quoi tu sers", "tu sers a quoi", "pourquoi as tu ete cree", "tu es cree pourquoi", "tu es creer pourquoi", "tu es creer pouauoi", "tu es cree pour quoi", "tu es creer pour quoi", "presente toi"}
    if simple in identities:
        return {"intention": "conversationnel", "confiance": 1.0, "parametres": {}, "parametres_manquants": [], "prefill": {}, "action_frontend": None,
                "reponse_vocale": "Je suis l’assistant FORMA-IA, conçu pour ALTIORA PREST. Je vous aide à consulter vos documents, expliquer les résultats de veille et exécuter les actions métier raccordées, comme lancer une détection ou créer une séance. S’il manque une information, je vous la demande. Les contenus destinés à un client restent soumis à votre validation."}
    salutations = {"bonjour", "bonsoir", "salut", "coucou", "merci", "au revoir"}
    if texte in salutations:
        return {
            "intention": "conversationnel",
            "confiance": 1.0,
            "parametres": {},
            "parametres_manquants": [],
            "reponse_vocale": "Bonjour, je suis l'assistant FORMA-IA. Que souhaitez-vous faire ?",
            "action_frontend": None,
            "prefill": {},
        }
    launches = {"lance la veille", "lance la veille marché", "lance la veille marche", "lance la détection", "lance la détection des opportunités", "détecte les opportunités", "detecte les opportunites", "démarre la veille", "demarre la veille"}
    opens = {"ouvre la veille", "ouvre la veille marché", "ouvre la veille marche", "affiche les opportunités", "affiche les opportunites"}
    if texte.rstrip(".!?") in launches | opens:
        launch = texte.rstrip(".!?") in launches
        return {"intention": "veille_marche" if launch else "afficher_opportunites", "confiance": 1.0,
                "parametres": {}, "parametres_manquants": [], "prefill": {},
                "action_frontend": "lancer_veille" if launch else "afficher_opportunites",
                "reponse_vocale": "Je lance la détection." if launch else "J'ouvre la veille marché."}
    if texte in {"annule", "annuler", "stop", "arrête", "arrete"}:
        return {
            "intention": "annuler",
            "confiance": 1.0,
            "parametres": {},
            "parametres_manquants": [],
            "reponse_vocale": "D'accord, aucune nouvelle action n'est lancée. Une opération déjà envoyée au serveur n'est pas annulée automatiquement.",
            "action_frontend": None,
            "prefill": {},
        }
    # Les demandes générales sur FORMA-IA sont routées sans LLM vers C3,
    # y compris la faute vocale fréquente « platforme ».
    if re.match(r"^(comment|explique|quels documents|où est expliqué|ou est explique)\b", texte):
        return {
            "intention": "question_rag",
            "confiance": 0.96,
            "parametres": {"type_demande": "aide_plateforme"},
            "parametres_manquants": [],
            "reponse_vocale": "Je vous guide sur l'utilisation de FORMA-IA.",
            "action_frontend": "ouvrir_chat_rag",
            "prefill": {},
        }
    return None


def _charger_prompt() -> dict:
    with open(_PROMPT_PATH, encoding="utf-8") as f:
        return yaml.safe_load(f)


def _construire_messages(commande: str, formations: list[str]) -> list[dict]:
    p = _charger_prompt()
    formations_str = ", ".join(formations) if formations else "aucune formation disponible"
    date_str = datetime.now(ZoneInfo("Indian/Antananarivo")).strftime("%A %d %B %Y")

    system = (
        f"{p['role']}\n\n"
        f"CONTEXTE PLATEFORME :\n{p['context']}\n\n"
        f"SÉCURITÉ :\n{p['securite']}\n\n"
        f"FORMAT DE RÉPONSE :\n{p['format']}\n\n"
        f"EXEMPLES :\n{p['exemples']}"
    ).replace("{{FORMATIONS_DISPONIBLES}}", formations_str).replace("{{DATE_ACTUELLE}}", date_str)

    user = p["tache"].replace("{{COMMANDE}}", commande).replace(
        "{{FORMATIONS_DISPONIBLES}}", formations_str
    ).replace("{{DATE_ACTUELLE}}", date_str)

    return [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]


async def router_commande(commande: str, formations: list[str] | None = None) -> dict:
    """
    Analyse une commande vocale et retourne l'intention + action frontend.

    Args:
        commande: Texte transcrit depuis la voix de l'utilisateur.
        formations: Liste des noms de formations disponibles (contexte).

    Returns:
        Dict avec intention, parametres, reponse_vocale, action_frontend, prefill.
    """
    if not commande or not commande.strip():
        return {
            "intention": "hors_perimetre",
            "confiance": 1.0,
            "parametres": {},
            "parametres_manquants": [],
            "reponse_vocale": "Je n'ai pas compris votre demande. Pouvez-vous répéter ?",
            "action_frontend": None,
            "prefill": {},
        }

    reponse_locale = _reponse_locale(commande)
    if reponse_locale is not None:
        return reponse_locale

    llm = get_llm_provider()
    messages = _construire_messages(commande.strip(), formations or [])

    try:
        response = await llm.generate(
            system_prompt=messages[0]["content"],
            user_prompt=messages[1]["content"],
            temperature=0.1,
            max_tokens=512,
            json_mode=True,
            reasoning_effort="low",
        )
        result = json.loads(response["content"])
        if not isinstance(result, dict):
            raise ValueError("Objet JSON attendu")
        # Validation minimale des champs obligatoires
        for champ in ("intention", "reponse_vocale", "action_frontend", "prefill"):
            if champ not in result:
                raise ValueError(f"Champ manquant dans la réponse : {champ}")
        intentions = {
            "veille_marche": "lancer_veille", "generer_tdr": "ouvrir_formulaire_tdr",
            "generer_offre": "ouvrir_formulaire_offre", "creer_seance": "ouvrir_formulaire_seance",
            "creer_session": "ouvrir_formulaire_session",
            "generer_attestation": "ouvrir_formulaire_attestation", "relance_facture": "ouvrir_facturation",
            "question_rag": "ouvrir_chat_rag", "afficher_opportunites": "afficher_opportunites",
            "afficher_sessions": "afficher_sessions", "afficher_validations": "afficher_validations",
            "hors_perimetre": None,
            "conversationnel": None, "annuler": None,
        }
        if not isinstance(result["intention"], str) or result["intention"] not in intentions:
            raise ValueError("Intention inconnue")
        confiance = result.get("confiance", 0)
        if not isinstance(confiance, (float, int)) or not 0 <= confiance <= 1:
            raise ValueError("Confiance invalide")
        for field in ("parametres", "prefill"):
            if not isinstance(result.get(field, {}), dict):
                raise ValueError("Paramètres invalides")
        if not isinstance(result.get("parametres_manquants", []), list) or not all(
            isinstance(champ, str) for champ in result.get("parametres_manquants", [])
        ):
            raise ValueError("Liste des paramètres manquants invalide")
        if not isinstance(result["reponse_vocale"], str):
            raise ValueError("Réponse textuelle attendue")
        result["action_frontend"] = intentions[result["intention"]]
        if result.get("parametres_manquants") or confiance < 0.7:
            result["action_frontend"] = None
        return result

    except (json.JSONDecodeError, ValueError) as e:
        logger.warning("Réponse LLM invalide pour commande vocale : %s", e)
        return {
            "intention": "hors_perimetre",
            "confiance": 0.0,
            "parametres": {},
            "parametres_manquants": [],
            "reponse_vocale": "Je n'ai pas pu analyser votre demande. Veuillez réessayer.",
            "action_frontend": None,
            "prefill": {},
        }
    except LLMError as e:
        logger.error("Erreur LLM routeur vocal : %s", e)
        raise
