# app/services/rag/query_cache_service.py
# ============================================================
# CACHE DES EMBEDDINGS DE REQUÊTES — data/rag/query_cache.json (Étape D)
# ============================================================
# Consulté AVANT tout appel Voyage (mission C3) : indispensable au palier
# gratuit (3 RPM/10 000 TPM) pour les questions répétées (démonstration,
# évaluation). Clé = texte normalisé + modèle de requête (un même texte
# avec 2 modèles différents = 2 entrées, car pas le même vecteur).
# ============================================================

import json
import logging
import os
import re
import unicodedata
from difflib import SequenceMatcher
from pathlib import Path
from typing import Callable, List, Optional

logger = logging.getLogger(__name__)

CHEMIN_CACHE_DEFAUT = Path(__file__).resolve().parents[3] / "data" / "rag" / "query_cache.json"

_ESPACES_MULTIPLES = re.compile(r"\s+")
_PONCTUATION = re.compile(r"[^\w\s]", re.UNICODE)
_STOP_WORDS = {"a", "au", "aux", "avec", "comment", "de", "des", "du", "en", "est", "et", "la", "le", "les", "moi", "mon", "nos", "notre", "ou", "par", "pour", "que", "quel", "quelle", "quelles", "quels", "sur", "un", "une", "vous", "vos", "dans", "ce", "cette", "ces"}


def _resoudre_chemin(chemin: Path | None) -> Path:
    """Sépare le cache de questions par entreprise lorsqu'un tenant est actif."""
    chemin = chemin or CHEMIN_CACHE_DEFAUT
    if chemin == CHEMIN_CACHE_DEFAUT:
        try:
            from app.core.tenant_context import get_tenant_id
            tenant_id = get_tenant_id()
        except Exception:
            tenant_id = None
        if tenant_id is not None:
            return chemin.parent / "tenants" / str(tenant_id) / chemin.name
    return chemin


def normaliser_texte(texte: str) -> str:
    """Normalise les variantes typographiques d'une même question."""
    texte = unicodedata.normalize("NFKD", texte.strip().lower())
    texte = "".join(c for c in texte if not unicodedata.combining(c))
    texte = _PONCTUATION.sub(" ", texte)
    return _ESPACES_MULTIPLES.sub(" ", texte).strip()


def _cle(texte: str, modele_requete: str) -> str:
    return f"{modele_requete}::{normaliser_texte(texte)}"


def _charger(chemin: Path) -> dict:
    if not chemin.exists():
        return {}
    try:
        with open(chemin, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (json.JSONDecodeError, OSError) as exc:
        logger.error(f"❌ Cache de requêtes RAG illisible : {exc}")
        return {}


def _sauvegarder(cache: dict, chemin: Path) -> None:
    chemin.parent.mkdir(parents=True, exist_ok=True)
    tmp = chemin.with_suffix(".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False)
    os.replace(tmp, chemin)


def depuis_cache(texte: str, modele_requete: str, chemin: Path | None = None) -> list[float] | None:
    """Retourne un vecteur exact ou quasi-identique du même modèle.

    Le rapprochement est volontairement conservateur : la similarité
    textuelle seule ne suffit pas, les mots significatifs doivent également
    se recouper. Cela évite de réutiliser un embedding pour un autre sujet.
    """
    chemin = _resoudre_chemin(chemin)
    cache = _charger(chemin)
    cle = _cle(texte, modele_requete)
    if cle in cache:
        return cache[cle]

    requete = normaliser_texte(texte)
    mots = {mot for mot in requete.split() if mot not in _STOP_WORDS and len(mot) > 2}
    if len(requete) < 16 or not mots:
        return None

    prefixe = f"{modele_requete}::"
    meilleur_score = 0.0
    meilleur_vecteur = None
    for cle_candidate, vecteur in cache.items():
        if not cle_candidate.startswith(prefixe):
            continue
        candidate = normaliser_texte(cle_candidate[len(prefixe):])
        candidate_words = {mot for mot in candidate.split() if mot not in _STOP_WORDS and len(mot) > 2}
        if not candidate_words:
            continue
        chevauchement = len(mots & candidate_words) / max(len(mots | candidate_words), 1)
        similarite = SequenceMatcher(None, requete, candidate).ratio()
        score = max(similarite, chevauchement)
        if similarite >= 0.91 and chevauchement >= 0.68 and score > meilleur_score:
            meilleur_score, meilleur_vecteur = score, vecteur
    if meilleur_vecteur is not None:
        logger.debug("💾 Cache de requête quasi-identique : hit (score=%.3f)", meilleur_score)
        cache[cle] = meilleur_vecteur
        _sauvegarder(cache, chemin)
    return meilleur_vecteur


def mettre_en_cache(texte: str, modele_requete: str, vecteur: list[float], chemin: Path | None = None) -> None:
    chemin = _resoudre_chemin(chemin)
    cache = _charger(chemin)
    cache[_cle(texte, modele_requete)] = vecteur
    _sauvegarder(cache, chemin)


def taille_cache(chemin: Path | None = None) -> int:
    return len(_charger(_resoudre_chemin(chemin)))


async def obtenir_ou_calculer(
    texte: str,
    modele_requete: str,
    fonction_embed_query: Callable,
    chemin: Path | None = None,
    **kwargs_embed,
) -> list[float]:
    """
    Consulte le cache AVANT tout appel Voyage. `fonction_embed_query` a la
    signature de embedding_service.embed_query (async, texte, **kwargs).
    """
    en_cache = depuis_cache(texte, modele_requete, chemin)
    if en_cache is not None:
        logger.debug("💾 Cache de requête : hit")
        return en_cache

    vecteur = await fonction_embed_query(texte, **kwargs_embed)
    mettre_en_cache(texte, modele_requete, vecteur, chemin)
    return vecteur
