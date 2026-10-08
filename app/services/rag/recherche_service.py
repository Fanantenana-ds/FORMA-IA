# app/services/rag/recherche_service.py
# ============================================================
# SERVICE — Recherche vectorielle (RAG, Étape D)
# ============================================================
# Similarité cosinus via pgvector (1 - distance cosinus). Vérifie la
# compatibilité de VOYAGE_MODEL_QUERY avec les modèles déjà présents en
# base AVANT toute recherche (mission C3) ; consulte le cache de requêtes
# AVANT tout appel Voyage. L'accès base passe par KnowledgeRepository
# (comme rag_orchestrator) pour rester testable "sans base".
# ============================================================

import logging
import os
from dataclasses import dataclass
from typing import List, Optional

from app.services.rag.embedding_provider import get_embedding_provider, verifier_compatibilite_famille
from app.services.rag.query_cache_service import obtenir_ou_calculer, CHEMIN_CACHE_DEFAUT
from app.services.rag.knowledge_repository import KnowledgeRepository

logger = logging.getLogger(__name__)

RAG_TOP_K_DEFAUT = int(os.getenv("RAG_TOP_K", "8"))
RAG_MIN_SCORE_DEFAUT = float(os.getenv("RAG_MIN_SCORE", "0.5"))

_repository_defaut = KnowledgeRepository()


class IncompatibiliteModeleError(Exception):
    """Message déjà en français — VOYAGE_MODEL_QUERY (ou le modèle
    d'indexation) hors famille des modèles déjà indexés en base."""


@dataclass
class ResultatRecherche:
    contenu: str
    score: float
    fichier: Optional[str]
    formation_code: Optional[str]
    formation_titre: Optional[str]
    collection: str
    page_debut: Optional[int]
    page_fin: Optional[int]
    type_support: Optional[str]


def verifier_compatibilite_avec_base(
    modele: str, collection: Optional[str] = None, repository: Optional[KnowledgeRepository] = None,
) -> None:
    """
    Lève IncompatibiliteModeleError (français) si `modele` n'est compatible
    avec AUCUN modèle déjà indexé en base pour cette collection. Base vide
    (ou aucun chunk de cette collection) -> rien à vérifier.
    """
    repo = repository or _repository_defaut
    modeles_en_base = set(repo.modeles_presents(collection))
    if not modeles_en_base:
        return

    erreurs = []
    for modele_indexe in modeles_en_base:
        try:
            verifier_compatibilite_famille(modele, modele_indexe)
        except ValueError as exc:
            erreurs.append(str(exc))

    if len(erreurs) == len(modeles_en_base):
        raise IncompatibiliteModeleError(
            f"Modèle '{modele}' incompatible avec tous les modèles déjà "
            f"indexés en base ({sorted(modeles_en_base)}). Opération refusée. "
            f"Détail : {erreurs[0]}"
        )


async def rechercher(
    requete: str,
    top_k: int = RAG_TOP_K_DEFAUT,
    collection: str = "support",
    formation_code: Optional[str] = None,
    domaine: Optional[str] = None,
    annee: Optional[int] = None,
    type_support: Optional[str] = None,
    seuil_min: Optional[float] = None,
    attente_max_s: Optional[float] = 5.0,
    repository: Optional[KnowledgeRepository] = None,
) -> List[ResultatRecherche]:
    """
    Recherche par similarité cosinus dans knowledge_base.

    Si, après filtrage par seuil_min, aucun résultat ne reste : retourne
    une liste VIDE (l'appelant — Étape E, chat — ne doit alors PAS appeler
    le LLM : "aucun support pertinent").
    """
    repo = repository or _repository_defaut
    seuil_min = RAG_MIN_SCORE_DEFAUT if seuil_min is None else seuil_min
    provider = get_embedding_provider()

    verifier_compatibilite_avec_base(provider.modele_requete, collection, repo)

    async def _embed(texte, **kw):
        return await provider.embed_query(texte, **kw)

    vecteur = await obtenir_ou_calculer(
        requete, provider.modele_requete, _embed,
        chemin=CHEMIN_CACHE_DEFAUT, attente_max_s=attente_max_s,
    )

    lignes = repo.rechercher_par_similarite(
        vecteur, collection, top_k,
        formation_code=formation_code, domaine=domaine, annee=annee, type_support=type_support,
    )

    resultats = []
    for ligne, dist in lignes:
        score = 1.0 - float(dist)
        if score < seuil_min:
            continue
        resultats.append(ResultatRecherche(
            contenu=ligne.contenu, score=round(score, 4), fichier=ligne.fichier,
            formation_code=ligne.formation_code, formation_titre=ligne.formation_titre,
            collection=ligne.collection, page_debut=ligne.page_debut, page_fin=ligne.page_fin,
            type_support=ligne.type_support,
        ))

    if not resultats:
        logger.info(f"ℹ️ Aucun support pertinent pour la requête (seuil={seuil_min}).")

    return resultats
