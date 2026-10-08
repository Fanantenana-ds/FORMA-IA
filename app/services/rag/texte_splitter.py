# app/services/rag/texte_splitter.py
# ============================================================
# DÉCOUPAGE RÉCURSIF DE TEXTE — Python pur (RAG, Étape C)
# ============================================================
# Remplace langchain_text_splitters.RecursiveCharacterTextSplitter.
#
# TROUVÉ EN ESSAYANT D'INDEXER LE GUIDE UTILISATEUR (2026-09-24) :
# langchain_text_splitters/__init__.py importe INCONDITIONNELLEMENT
# SentenceTransformersTokenTextSplitter, qui importe sentence_transformers
# -> transformers -> torch, MÊME pour n'utiliser que
# RecursiveCharacterTextSplitter. Or sentence-transformers/torch ont été
# retirés de requirements.txt à l'Étape B (remplacés par Voyage AI,
# bloqués par Smart App Control sur ce poste). Sur un venv propre suivant
# le requirements.txt actuel, TOUT le module RAG serait donc cassé dès
# l'import de chunking_service.py.
#
# Suit la consigne de la mission : dépendance bloquée -> alternative en
# Python pur, ne pas contourner. Réimplémentation fidèle de l'algorithme
# (découpe récursive par liste de séparateurs, fusion en chunks avec
# chevauchement) — aucune dépendance externe.
# ============================================================

from typing import List

SEPARATEURS_DEFAUT = ["\n\n", "\n", ". ", " ", ""]


def _decouper_par_separateur(texte: str, separateur: str) -> List[str]:
    if separateur:
        return texte.split(separateur)
    return list(texte)  # dernier recours : caractère par caractère


def _fusionner_morceaux(morceaux: List[str], separateur: str, taille: int, chevauchement: int) -> List[str]:
    """Fusionne des petits morceaux en chunks d'environ `taille` caractères,
    avec `chevauchement` caractères communs entre chunks consécutifs."""
    chunks: List[str] = []
    courant: List[str] = []
    longueur = 0
    len_sep = len(separateur)

    for morceau in morceaux:
        longueur_ajout = len(morceau) + (len_sep if courant else 0)

        if longueur + longueur_ajout > taille and courant:
            chunk = separateur.join(courant)
            if chunk:
                chunks.append(chunk)

            # Retire des morceaux du début jusqu'à repasser sous le chevauchement cible
            while courant and (longueur > chevauchement or (len(courant) > 1 and longueur + longueur_ajout > taille)):
                longueur -= len(courant[0]) + (len_sep if len(courant) > 1 else 0)
                courant.pop(0)

        courant.append(morceau)
        longueur += len(morceau) + (len_sep if len(courant) > 1 else 0)

    chunk = separateur.join(courant)
    if chunk:
        chunks.append(chunk)
    return chunks


def decouper_texte(
    texte: str,
    taille: int,
    chevauchement: int,
    separateurs: List[str] = None,
) -> List[str]:
    """
    Découpe `texte` en chunks d'environ `taille` caractères (chevauchement
    `chevauchement`), en essayant les séparateurs dans l'ordre donné
    (paragraphe, ligne, phrase, mot, caractère) — équivalent pur Python de
    RecursiveCharacterTextSplitter (mêmes séparateurs par défaut).
    """
    if not texte:
        return []

    separateurs = separateurs or SEPARATEURS_DEFAUT
    return _decouper_recursif(texte, separateurs, taille, chevauchement)


def _decouper_recursif(texte: str, separateurs: List[str], taille: int, chevauchement: int) -> List[str]:
    if not texte:
        return []

    separateur = separateurs[-1]
    reste_separateurs: List[str] = []
    for i, sep in enumerate(separateurs):
        if sep == "":
            separateur = sep
            reste_separateurs = []
            break
        if sep in texte:
            separateur = sep
            reste_separateurs = separateurs[i + 1:]
            break

    morceaux = _decouper_par_separateur(texte, separateur)

    resultat: List[str] = []
    a_fusionner: List[str] = []

    for morceau in morceaux:
        if len(morceau) < taille:
            a_fusionner.append(morceau)
            continue

        if a_fusionner:
            resultat.extend(_fusionner_morceaux(a_fusionner, separateur, taille, chevauchement))
            a_fusionner = []

        if not reste_separateurs:
            resultat.append(morceau)
        else:
            resultat.extend(_decouper_recursif(morceau, reste_separateurs, taille, chevauchement))

    if a_fusionner:
        resultat.extend(_fusionner_morceaux(a_fusionner, separateur, taille, chevauchement))

    return resultat
