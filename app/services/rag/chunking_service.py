# app/services/rag/chunking_service.py
# ============================================================
# SERVICE — Découpage en chunks (RAG, Étape C)
# ============================================================
# Deux stratégies distinctes (mission C3) :
#   - chunk_segments()    : PDF/DOCX/XLSX — découpage par TOKENS (≈700,
#     chevauchement 100), chaque chunk garde page_debut/page_fin.
#   - chunk_pptx_slides()  : PPTX — PAS de découpage par tokens, groupe
#     3 à 5 diapositives consécutives par chunk.
# chunk_text() : utilitaire générique conservé (découpage par caractères,
# pour un usage hors RAG structuré, ex. blocs de résumé Groq).
# ============================================================

import logging
import os
from dataclasses import dataclass
from typing import List

from app.services.rag.texte_splitter import decouper_texte
from app.services.rag.document_loader_service import Segment
from app.services.rag.embedding_provider import CARACTERES_PAR_TOKEN_ESTIME

logger = logging.getLogger(__name__)


@dataclass
class Chunk:
    """Un chunk prêt pour l'embedding, avec sa position dans le document
    source (page pour PDF/DOCX/XLSX, diapositives pour PPTX)."""
    texte: str
    page_debut: int
    page_fin: int
    chunk_index: int


# Paramètres par défaut (modifiables via .env) — en TOKENS, pas en caractères
DEFAULT_CHUNK_SIZE_TOKENS = int(os.getenv("RAG_CHUNK_SIZE_TOKENS", "700"))
DEFAULT_CHUNK_OVERLAP_TOKENS = int(os.getenv("RAG_CHUNK_OVERLAP_TOKENS", "100"))
DEFAULT_PPTX_SLIDES_MIN = int(os.getenv("RAG_PPTX_SLIDES_MIN", "3"))
DEFAULT_PPTX_SLIDES_MAX = int(os.getenv("RAG_PPTX_SLIDES_MAX", "5"))

_SEPARATEUR_SEGMENTS = "\n\n"


def _construire_texte_et_limites(segments: List[Segment]):
    """Concatène les segments et retient, pour chaque plage de caractères,
    le numéro de page/diapositive d'origine."""
    morceaux = []
    limites = []  # (debut, fin, numero)
    offset = 0

    for segment in segments:
        debut = offset
        morceaux.append(segment.texte)
        offset += len(segment.texte)
        limites.append((debut, offset, segment.numero))
        morceaux.append(_SEPARATEUR_SEGMENTS)
        offset += len(_SEPARATEUR_SEGMENTS)

    return "".join(morceaux), limites


def _numero_pour_offset(limites, offset: int) -> int:
    for debut, fin, numero in limites:
        if debut <= offset < fin:
            return numero
    return limites[-1][2] if limites else 1


def chunk_segments(
    segments: List[Segment],
    chunk_size_tokens: int = DEFAULT_CHUNK_SIZE_TOKENS,
    chunk_overlap_tokens: int = DEFAULT_CHUNK_OVERLAP_TOKENS,
) -> List[Chunk]:
    """
    Découpe une liste de segments (pages PDF, feuilles XLSX, ou le segment
    unique d'un DOCX) en chunks d'environ `chunk_size_tokens` tokens
    (estimation ≈4 caractères/token), avec chevauchement. Chaque chunk
    garde page_debut/page_fin (peut différer si le chunk chevauche une
    limite de page).
    """
    if not segments:
        return []

    taille_caracteres = chunk_size_tokens * CARACTERES_PAR_TOKEN_ESTIME
    chevauchement_caracteres = chunk_overlap_tokens * CARACTERES_PAR_TOKEN_ESTIME

    texte_complet, limites = _construire_texte_et_limites(segments)

    morceaux = decouper_texte(texte_complet, taille_caracteres, chevauchement_caracteres)
    morceaux = [m.strip() for m in morceaux if m.strip() and len(m.strip()) > 20]

    resultats = []
    position_recherche = 0

    for idx, morceau in enumerate(morceaux):
        pos = texte_complet.find(morceau, max(0, position_recherche - chevauchement_caracteres))
        if pos == -1:
            pos = texte_complet.find(morceau)
        if pos == -1:
            pos = position_recherche  # repli très improbable

        fin = pos + len(morceau)
        position_recherche = pos

        page_debut = _numero_pour_offset(limites, pos)
        page_fin = _numero_pour_offset(limites, max(pos, fin - 1))

        resultats.append(Chunk(
            texte=morceau, page_debut=page_debut, page_fin=page_fin, chunk_index=idx,
        ))

    logger.info(
        f"✂️ Chunking (tokens) : {len(segments)} segment(s) → {len(resultats)} chunk(s) "
        f"(≈{chunk_size_tokens} tokens, chevauchement {chunk_overlap_tokens})"
    )
    return resultats


def chunk_pptx_slides(
    segments: List[Segment],
    slides_min: int = DEFAULT_PPTX_SLIDES_MIN,
    slides_max: int = DEFAULT_PPTX_SLIDES_MAX,
) -> List[Chunk]:
    """
    PPTX uniquement : groupe `slides_min` à `slides_max` diapositives
    consécutives par chunk (PAS de découpage par tokens — la mission le
    demande explicitement, une diapositive formant une unité de sens).

    Simplification documentée : si le dernier groupe restant est plus petit
    que `slides_min`, il est absorbé dans le groupe précédent plutôt que
    laissé seul (un chunk peut alors dépasser `slides_max`).
    """
    if not segments:
        return []

    groupes: List[List[Segment]] = []
    i = 0
    n = len(segments)

    while i < n:
        fin = min(i + slides_max, n)
        if 0 < (n - fin) < slides_min:
            fin = n  # absorbe le reliquat trop petit
        groupes.append(segments[i:fin])
        i = fin

    resultats = []
    for idx, groupe in enumerate(groupes):
        texte = "\n\n".join(f"[Diapositive {s.numero}]\n{s.texte}" for s in groupe)
        resultats.append(Chunk(
            texte=texte,
            page_debut=groupe[0].numero,
            page_fin=groupe[-1].numero,
            chunk_index=idx,
        ))

    logger.info(
        f"✂️ Chunking (PPTX) : {len(segments)} diapositive(s) → {len(resultats)} chunk(s) "
        f"({slides_min}-{slides_max} diapositives/chunk)"
    )
    return resultats


# ============================================================
# UTILITAIRE GÉNÉRIQUE — découpage par caractères (hors RAG structuré)
# ============================================================

DEFAULT_CHUNK_SIZE = int(os.getenv("RAG_CHUNK_SIZE", "1000"))
DEFAULT_CHUNK_OVERLAP = int(os.getenv("RAG_CHUNK_OVERLAP", "200"))


def chunk_text(
    text: str,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    chunk_overlap: int = DEFAULT_CHUNK_OVERLAP,
) -> List[str]:
    """Découpage générique par caractères (ex. blocs pour résumé Groq d'un
    document long) — ne garde PAS la page d'origine, contrairement à
    chunk_segments()."""
    if not text:
        return []

    chunks = decouper_texte(text, chunk_size, chunk_overlap)
    chunks = [c.strip() for c in chunks if c.strip() and len(c.strip()) > 20]

    logger.info(
        f"✂️ Chunking (caractères) : {len(text)} chars → {len(chunks)} chunks "
        f"(size={chunk_size}, overlap={chunk_overlap})"
    )

    return chunks
