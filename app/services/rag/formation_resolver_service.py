# app/services/rag/formation_resolver_service.py
# ============================================================
# RÉSOLUTION DU NOM DE FORMATION — Étape E (chat)
# ============================================================
# Compare le texte au code, au titre et aux synonymes du catalogue avec
# difflib (module standard, pas de dépendance bloquée), insensible à la
# casse ET aux accents ("IA FONDEMANTAL" -> IA_FONDAMENTAUX).
# ============================================================

import difflib
import logging
import unicodedata
from dataclasses import dataclass, field
from typing import List, Optional

from app.services.rag.catalogue_service import Formation, charger_catalogue

logger = logging.getLogger(__name__)

SEUIL_RESOLUTION = 0.6  # ratio difflib (0-1) minimum pour retenir un candidat
ECART_AMBIGUITE = 0.08  # 2 candidats à moins de cet écart -> ambigu


def _sans_accents(texte: str) -> str:
    """Retire les accents (NFD puis filtre les marques combinantes)."""
    nfkd = unicodedata.normalize("NFKD", texte)
    return "".join(c for c in nfkd if not unicodedata.combining(c))


def _normaliser(texte: str) -> str:
    return _sans_accents(texte).lower().strip()


@dataclass
class ResolutionFormation:
    statut: str  # "trouvee" | "ambigue" | "aucune"
    formation: Optional[Formation] = None
    candidats: List[Formation] = field(default_factory=list)  # si ambigue
    score: float = 0.0


def _libelles_formation(formation: Formation) -> List[str]:
    """Tous les libellés comparables d'une formation : code, titre, synonymes."""
    return [formation.code, formation.titre, *formation.synonymes]


def _mots_significatifs(libelle: str) -> set:
    """Mots du libellé (code/titre/synonyme), underscores traités comme
    des espaces, mots de 3 lettres ou moins ignorés (trop génériques)."""
    normalise = _normaliser(libelle).replace("_", " ").replace(":", " ")
    return {m for m in normalise.split() if len(m) > 3}


def _score_mots_communs(texte_normalise: str, libelle: str) -> float:
    """Proportion des mots significatifs du libellé présents dans le texte
    — robuste pour une vraie phrase de chat ('le contenu de la formation
    IA fondamentaux'), là où un ratio caractère-à-caractère sur la phrase
    entière serait beaucoup trop dilué."""
    mots_libelle = _mots_significatifs(libelle)
    if not mots_libelle:
        return 0.0
    mots_texte = set(texte_normalise.replace("_", " ").split())
    communs = mots_libelle & mots_texte
    return 0.9 * (len(communs) / len(mots_libelle))


def _meilleur_score(texte_normalise: str, formation: Formation) -> float:
    scores = [
        difflib.SequenceMatcher(None, texte_normalise, _normaliser(libelle)).ratio()
        for libelle in _libelles_formation(formation)
    ]
    for libelle in _libelles_formation(formation):
        libelle_normalise = _normaliser(libelle).replace("_", " ")
        # Bonus si le libellé est explicitement CONTENU dans le texte (ex. code exact cité)
        if libelle_normalise and libelle_normalise in texte_normalise.replace("_", " "):
            scores.append(0.95)
        # Bonus proportionnel aux mots du libellé retrouvés dans le texte
        scores.append(_score_mots_communs(texte_normalise, libelle))
    return max(scores) if scores else 0.0


def resoudre_formation(texte: str, chemin_catalogue=None) -> ResolutionFormation:
    """
    Résout un nom de formation approximatif vers une formation du
    catalogue.

    - Un seul résultat nettement au-dessus du seuil -> "trouvee".
    - Plusieurs candidats proches -> "ambigue" (demande de précision).
    - Aucun -> "aucune" (proposer la liste des formations).
    """
    formations = charger_catalogue(chemin_catalogue)
    if not formations:
        return ResolutionFormation(statut="aucune")

    texte_normalise = _normaliser(texte)
    scores = [(f, _meilleur_score(texte_normalise, f)) for f in formations]
    scores.sort(key=lambda x: x[1], reverse=True)

    meilleur_formation, meilleur_score = scores[0]

    if meilleur_score < SEUIL_RESOLUTION:
        return ResolutionFormation(statut="aucune", candidats=formations, score=meilleur_score)

    proches = [f for f, s in scores if meilleur_score - s <= ECART_AMBIGUITE]

    if len(proches) > 1:
        return ResolutionFormation(statut="ambigue", candidats=proches, score=meilleur_score)

    return ResolutionFormation(statut="trouvee", formation=meilleur_formation, score=meilleur_score)
