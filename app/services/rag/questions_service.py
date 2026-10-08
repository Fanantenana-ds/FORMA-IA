# app/services/rag/questions_service.py
# ============================================================
# SERVICE — Génération de questions (RAG, Étape G)
# ============================================================
# Usage interne, PAS de HITL (mission).
# ============================================================

import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


async def generer_questions(
    formation_code: str,
    formation_titre: str,
    appeler_llm_json,
    nb_questions_max: int = 10,
    repository=None,
) -> Dict[str, Any]:
    """Génère des questions de révision à partir des supports indexés
    d'une formation. Retourne une liste vide si aucun contenu n'est
    indexé (MODE STRICT : jamais de question inventée)."""
    from app.services.rag import recherche_service as recherche

    resultats_rag = await recherche.rechercher(
        formation_titre, collection="support", formation_code=formation_code,
        top_k=nb_questions_max, attente_max_s=None, repository=repository,
    )

    if not resultats_rag:
        return {"questions": [], "message": "Aucun support indexé pour cette formation."}

    contexte = "\n\n".join(f"[{r.fichier}, p. {r.page_debut}]\n{r.contenu}" for r in resultats_rag)
    resultat_llm = await appeler_llm_json("questions.yaml", contexte)

    if not resultat_llm:
        return {"questions": [], "message": "Génération LLM indisponible."}

    return {"questions": resultat_llm.get("questions", []), "message": None}
