# app/services/rag/resume_service.py
# ============================================================
# SERVICE — Résumés Groq (par support, puis par formation)
# ============================================================
# Étape C §9-10 de la mission RAG. Passe TOUJOURS par le Provider
# Abstraction (get_llm_provider), jamais d'appel direct. Si Groq échoue à
# quelque étape que ce soit : ne lève PAS d'exception (le document reste
# indexé), retourne None — l'appelant (rag_orchestrator) doit alors laisser
# resume_statut="a_generer" (voir registry_service).
# ============================================================

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

from app.services.llm import get_llm_provider, LLMNotAvailableError
from app.services.rag.document_loader_service import Segment
from app.services.rag.chunking_service import chunk_text

logger = logging.getLogger(__name__)

_DOSSIER_PROMPTS = Path(__file__).resolve().parents[2] / "prompts" / "rag"
SEUIL_RESUME_DIRECT_CARACTERES = 12_000
TAILLE_BLOC_CARACTERES = 8_000


def _charger_prompt(nom_fichier: str) -> str:
    with open(_DOSSIER_PROMPTS / nom_fichier, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    sections = [data.get(cle, "") for cle in ("role", "tache", "format", "contraintes", "exemples")]
    return "\n\n".join(s for s in sections if s)


def _texte_segments(segments: List[Segment]) -> str:
    return "\n\n".join(f"[Page/Diapositive {s.numero}]\n{s.texte}" for s in segments)


async def _appeler_llm(system_prompt: str, contenu: str) -> Optional[Dict[str, Any]]:
    try:
        llm = get_llm_provider()
    except LLMNotAvailableError:
        logger.warning("⚠️ Résumé RAG : aucun fournisseur LLM disponible.")
        return None

    try:
        reponse = await llm.generate_with_retry(
            system_prompt=system_prompt,
            user_prompt=f"CONTENU À RÉSUMER :\n\n{contenu}",
            temperature=0.3,
            max_tokens=2000,
            json_mode=True,
            max_retries=2,
            # Modèle de raisonnement Groq (openai/gpt-oss-20b) : sans ceci,
            # le budget de tokens peut être épuisé par le raisonnement
            # interne avant l'émission du JSON (même défaut documenté et
            # corrigé pour M1, voir llm_analysis_service.py).
            reasoning_effort="low",
        )
        return json.loads(reponse["content"])
    except (json.JSONDecodeError, KeyError) as exc:
        logger.warning(f"⚠️ Résumé RAG : réponse LLM invalide ({exc}).")
        return None
    except Exception as exc:
        logger.warning(f"⚠️ Résumé RAG : appel LLM échoué ({type(exc).__name__} — {exc}).")
        return None


async def generer_resume_support(
    segments: List[Segment], titre_fichier: str
) -> Optional[Dict[str, Any]]:
    """
    Résume UN support (§9). Retourne {"resume", "plan", "mots_cles"} ou
    None si Groq échoue (le document reste indexé quand même, voir
    rag_orchestrator).

    Document long (> SEUIL_RESUME_DIRECT_CARACTERES) : résumé par blocs
    puis fusion, comme demandé.
    """
    if not segments:
        return None

    system_prompt = _charger_prompt("resume_support.yaml")
    texte_complet = _texte_segments(segments)

    if len(texte_complet) <= SEUIL_RESUME_DIRECT_CARACTERES:
        return await _appeler_llm(system_prompt, texte_complet)

    logger.info(
        f"📄 Résumé par blocs pour '{titre_fichier}' "
        f"({len(texte_complet)} caractères)"
    )
    blocs = chunk_text(texte_complet, chunk_size=TAILLE_BLOC_CARACTERES, chunk_overlap=0)

    resumes_blocs = []
    for bloc in blocs:
        resultat_bloc = await _appeler_llm(system_prompt, bloc)
        if resultat_bloc and resultat_bloc.get("resume"):
            resumes_blocs.append(resultat_bloc["resume"])

    if not resumes_blocs:
        return None

    texte_fusion = "\n\n".join(resumes_blocs)
    return await _appeler_llm(system_prompt, texte_fusion)


async def generer_resume_formation(
    formation_titre: str, resumes_supports: List[str]
) -> Optional[str]:
    """Résume UNE formation (§10) à partir des résumés de ses supports déjà
    générés. Retourne le texte du résumé, ou None si Groq échoue."""
    if not resumes_supports:
        return None

    system_prompt = _charger_prompt("resume_formation.yaml")
    contenu = "\n\n".join(f"- {r}" for r in resumes_supports)

    resultat = await _appeler_llm(system_prompt, f"Formation : {formation_titre}\n\n{contenu}")
    return resultat.get("resume") if resultat else None
