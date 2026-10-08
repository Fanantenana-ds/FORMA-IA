# app/services/rag/type_detection_service.py
# ============================================================
# DÉTECTION DU TYPE DE MESSAGE (RAG, Étape E §2)
# ============================================================
# 3 niveaux, dans l'ordre : (1) filtre Python (re) pour le conversationnel
# ÉVIDENT, (2) LLM en json_mode, (3) repli sur des règles Python par
# mots-clés si le LLM échoue. Une question de connaissance n'est JAMAIS
# classée conversationnelle, même précédée d'une salutation.
# ============================================================

import json
import logging
import re
import unicodedata
from pathlib import Path
from typing import Optional

import yaml

from app.services.llm import get_llm_provider, LLMNotAvailableError

logger = logging.getLogger(__name__)

TYPES_VALIDES = (
    "catalogue", "inventaire", "contenu_formation", "synthese_thematique",
    "localisation", "question_fond", "aide_plateforme", "conversationnel", "hors_sujet",
)

_DOSSIER_PROMPTS = Path(__file__).resolve().parents[2] / "prompts" / "rag"

# ── Niveau 1 : filtre Python pour le conversationnel évident ──
# Ne matche que des messages COURTS et PURS (rien d'autre dans le message) :
# une vraie question après une salutation doit être classée ailleurs.
_PATTERNS_CONVERSATIONNEL = [
    r"(bonjour|salut|bonsoir|coucou|hello|hi|bonne journ[ée]e|bonne soir[ée]e)",
    r"(merci( beaucoup| bien)?)",
    r"(au revoir|[àa] bient[ôo]t|bye|[àa] plus)",
    r"(qui es[ -]tu|que (sais|peux)[ -]tu faire|comment (tu fonctionnes|[çc]a marche)|"
    r"(c'est quoi|qu'est-ce que) (toi|cet assistant))",
]
_REGEX_CONVERSATIONNEL = re.compile(
    "^(" + "|".join(_PATTERNS_CONVERSATIONNEL) + r")[\s!?.,]*$", re.IGNORECASE,
)


def _normaliser(texte: str) -> str:
    nfkd = unicodedata.normalize("NFKD", texte)
    sans_accents = "".join(c for c in nfkd if not unicodedata.combining(c))
    return sans_accents.lower().strip()


def filtre_conversationnel_evident(message: str) -> bool:
    """True si le message est PUREMENT une salutation/remerciement/question
    sur l'assistant — rien d'autre dedans."""
    return bool(_REGEX_CONVERSATIONNEL.match(_normaliser(message)))


def _charger_prompt() -> str:
    with open(_DOSSIER_PROMPTS / "detection_type.yaml", "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    sections = [data.get(cle, "") for cle in ("role", "tache", "format", "exemples")]
    return "\n\n".join(s for s in sections if s)


async def _detecter_via_llm(message: str) -> Optional[str]:
    try:
        llm = get_llm_provider()
    except LLMNotAvailableError:
        return None

    try:
        reponse = await llm.generate_with_retry(
            system_prompt=_charger_prompt(),
            user_prompt=f"Message : {message}",
            temperature=0.0,
            max_tokens=300,  # modèle de raisonnement Groq : 50 était insuffisant (voir resume_service.py)
            json_mode=True,
            max_retries=2,
            reasoning_effort="low",
        )
        type_detecte = json.loads(reponse["content"]).get("type")
        return type_detecte if type_detecte in TYPES_VALIDES else None
    except Exception as exc:
        logger.warning(f"⚠️ Détection de type LLM échouée : {type(exc).__name__} — {exc}")
        return None


# ── Niveau 3 : repli par mots-clés (LLM indisponible/échoué) ──
_MOTS_CLES = {
    "catalogue": ("catalogue", "quelles formations", "liste des formations", "formations disponibles", "formations proposez"),
    "inventaire": ("inventaire", "documents indexes", "supports indexes", "combien de documents", "combien de supports"),
    "synthese_thematique": ("resume des formations", "formations concernant", "thematique", "synthese"),
    "localisation": ("ou est", "ou se trouve", "ou est explique", "quelle page", "quelle diapositive"),
    "contenu_formation": ("contenu de", "contenus de", "supports de la formation", "que contient la formation"),
    "aide_plateforme": ("valider", "hitl", "relance", "facture", "plateforme", "forma-ia", "comment faire pour"),
}


def detecter_type_regles(message: str) -> str:
    """Repli déterministe si le LLM est indisponible ou échoue. Par défaut :
    question_fond (la recherche vectorielle + le mode strict géreront
    naturellement les cas hors sujet en l'absence de contexte pertinent)."""
    normalise = _normaliser(message)
    for type_cible, mots in _MOTS_CLES.items():
        if any(mot in normalise for mot in mots):
            return type_cible
    return "question_fond"


async def detecter_type(message: str) -> str:
    """Point d'entrée : filtre Python -> LLM -> repli par règles."""
    if filtre_conversationnel_evident(message):
        return "conversationnel"

    type_llm = await _detecter_via_llm(message)
    if type_llm:
        return type_llm

    return detecter_type_regles(message)
