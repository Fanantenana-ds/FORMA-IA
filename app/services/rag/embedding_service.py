# app/services/rag/embedding_service.py
# ============================================================
# SERVICE — Embeddings (façade publique)
# ============================================================
# Délègue au fournisseur actif (Voyage AI via Provider Abstraction, voir
# embedding_provider.py). Signature publique conservée : embed_texts().
# Ajout : embed_query() (mode "query", distinct du mode "document").
#
# CHANGEMENT PAR RAPPORT À LA VERSION SENTENCE-TRANSFORMERS : embed_texts()
# devient async (obligatoire : appel HTTP réseau au lieu d'un modèle local).
# Tout appelant doit désormais faire `await embed_texts(...)`.
# ============================================================

import logging
from typing import List, Optional

from app.services.rag.embedding_provider import get_embedding_provider

logger = logging.getLogger(__name__)


async def embed_texts(texts: List[str]) -> List[List[float]]:
    """Vectorise une liste de textes en mode DOCUMENT (indexation)."""
    provider = get_embedding_provider()
    return await provider.embed_documents(texts)


async def embed_query(
    text: str, *, attente_max_s: Optional[float] = 5.0
) -> List[float]:
    """
    Vectorise une requête en mode QUERY (recherche/chat).

    attente_max_s=5.0 par défaut (chat, jamais d'écran figé) ; les scripts
    hors chat (évaluation, préchauffage du cache) peuvent passer None pour
    attendre le temps nécessaire sans limite.
    """
    provider = get_embedding_provider()
    return await provider.embed_query(text, attente_max_s=attente_max_s)
