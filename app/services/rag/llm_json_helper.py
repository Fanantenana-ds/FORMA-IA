# app/services/rag/llm_json_helper.py
# ============================================================
# HELPER PARTAGÉ — appel LLM en json_mode pour les prompts RAG
# ============================================================
# Utilisé par chat_orchestrator.py ET rag_orchestrator.py (portfolio,
# syllabus, questions) pour éviter la duplication.
# ============================================================

import json
import logging
from pathlib import Path
from typing import Any, Dict, Optional

import yaml

from app.services.llm import get_llm_provider, LLMNotAvailableError

logger = logging.getLogger(__name__)

_DOSSIER_PROMPTS = Path(__file__).resolve().parents[2] / "prompts" / "rag"


def charger_prompt(nom_fichier: str) -> str:
    with open(_DOSSIER_PROMPTS / nom_fichier, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    sections = [data.get(cle, "") for cle in ("role", "tache", "format", "contraintes", "exemples")]
    return "\n\n".join(s for s in sections if s)


async def appeler_llm_json(nom_prompt: str, contenu: str, max_tokens: int = 2000) -> Optional[Dict[str, Any]]:
    """
    Appelle le LLM en json_mode avec le prompt RTFCE `nom_prompt`, retourne
    le JSON parsé ou None (LLM indisponible/erreur/JSON invalide — jamais
    d'exception remontée à l'appelant, mission : "Groq indisponible :
    message clair, aucune donnée factice" -> l'appelant doit alors utiliser
    "[À compléter]", pas planter).
    """
    try:
        llm = get_llm_provider()
    except LLMNotAvailableError:
        logger.warning(f"⚠️ RAG : aucun fournisseur LLM disponible pour {nom_prompt}.")
        return None

    try:
        reponse = await llm.generate_with_retry(
            system_prompt=charger_prompt(nom_prompt),
            user_prompt=contenu,
            temperature=0.3,
            max_tokens=max_tokens,
            json_mode=True,
            max_retries=2,
            # Modèle de raisonnement Groq (openai/gpt-oss-20b) : sans ceci,
            # le budget de tokens peut être épuisé par le raisonnement
            # interne avant l'émission du JSON (bug réel rencontré et
            # corrigé le 2026-09-24, voir trace-claude.ps1).
            reasoning_effort="low",
        )
        return json.loads(reponse["content"])
    except Exception as exc:
        logger.warning(f"⚠️ RAG : appel LLM échoué ({nom_prompt}) : {type(exc).__name__} — {exc}")
        return None
