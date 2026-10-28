"""Agent de routage vocal FORMA-IA.

Reçoit une commande texte (issue de la reconnaissance vocale),
détecte l'intention, extrait les paramètres et retourne l'action
à exécuter sur le frontend ainsi que la réponse vocale.
"""

import json
import logging
from datetime import date
from pathlib import Path

import yaml

from app.services.llm.llm_factory import get_llm_provider
from app.services.llm.llm_provider import LLMError

logger = logging.getLogger(__name__)

_PROMPT_PATH = Path(__file__).parent.parent.parent / "prompts" / "vocal" / "routeur.yaml"


def _charger_prompt() -> dict:
    with open(_PROMPT_PATH, encoding="utf-8") as f:
        return yaml.safe_load(f)


def _construire_messages(commande: str, formations: list[str]) -> list[dict]:
    p = _charger_prompt()
    formations_str = ", ".join(formations) if formations else "aucune formation disponible"
    date_str = date.today().strftime("%A %d %B %Y")

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

    llm = get_llm_provider()
    messages = _construire_messages(commande.strip(), formations or [])

    try:
        raw = await llm.chat(
            messages=messages,
            temperature=0.1,
            max_tokens=512,
            reasoning_effort="low",
        )
        result = json.loads(raw)
        # Validation minimale des champs obligatoires
        for champ in ("intention", "reponse_vocale", "action_frontend", "prefill"):
            if champ not in result:
                raise ValueError(f"Champ manquant dans la réponse : {champ}")
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
