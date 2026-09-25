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
from pathlib import Path
from typing import Callable, List, Optional

logger = logging.getLogger(__name__)

CHEMIN_CACHE_DEFAUT = Path(__file__).resolve().parents[3] / "data" / "rag" / "query_cache.json"

_ESPACES_MULTIPLES = re.compile(r"\s+")


def normaliser_texte(texte: str) -> str:
    """Normalisation simple et déterministe : minuscules, espaces
    multiples réduits, bords coupés. Pas d'suppression d'accents (le
    français distingue des mots par les accents)."""
    return _ESPACES_MULTIPLES.sub(" ", texte.strip().lower())


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


def depuis_cache(texte: str, modele_requete: str, chemin: Optional[Path] = None) -> Optional[List[float]]:
    """Retourne le vecteur en cache, ou None si absent."""
    chemin = chemin or CHEMIN_CACHE_DEFAUT
    cache = _charger(chemin)
    return cache.get(_cle(texte, modele_requete))


def mettre_en_cache(texte: str, modele_requete: str, vecteur: List[float], chemin: Optional[Path] = None) -> None:
    chemin = chemin or CHEMIN_CACHE_DEFAUT
    cache = _charger(chemin)
    cache[_cle(texte, modele_requete)] = vecteur
    _sauvegarder(cache, chemin)


def taille_cache(chemin: Optional[Path] = None) -> int:
    return len(_charger(chemin or CHEMIN_CACHE_DEFAUT))


async def obtenir_ou_calculer(
    texte: str,
    modele_requete: str,
    fonction_embed_query: Callable,
    chemin: Optional[Path] = None,
    **kwargs_embed,
) -> List[float]:
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
