
# # app/services/veille/prefilter_service.py
# # ============================================================
# # SERVICE PRÉFILTRAGE — décision déterministe Python
# # ============================================================
# # Réduit les résultats Tavily (souvent 8-10) au maximum de
# # sources pertinentes à envoyer au LLM (MAX_RESULTS_AI, défaut 4).
# # Aucun appel LLM ici : uniquement des règles Python explicites,
# # donc reproductible et rapide (pas de coût de latence).
# # ============================================================

# import logging
# import os
# import re
# from typing import Any, Dict, List

# logger = logging.getLogger(__name__)

# MAX_RESULTS_AI = int(os.getenv("MAX_RESULTS_AI", "4"))

# # Termes techniques génériques toujours pertinents pour ALTIORA,
# # en complément des mots de la requête utilisateur.
# GENERIC_RELEVANT_TERMS = {
#     "ia", "data", "n8n", "automatisation", "automation",
#     "no-code", "low-code", "python", "react", "fastapi", "llm",
#     "machine learning", "développeur", "developer",
#     "cdi", "cdd", "stage", "freelance",
# }

# ACTION_INDICATORS = {
#     "cdi", "cdd", "stage", "freelance", "mission", "recrute",
#     "recrutement", "postuler", "appel d'offres",
# }

# # Patterns de pages génériques à rejeter AVANT même le classement —
# # ce ne sont jamais des opportunités précises, inutile de gaspiller
# # un appel Groq dessus (cf. diagnostic : "10 → 10 classés" alors que
# # ces pages devraient être éliminées en amont, pas juste mal notées).
# HARD_REJECT_PATTERNS = [
#     r"plus de\s+\d+\s*000?\s*(emplois|offres)",  # "plus de 1 000 emplois"
#     r"\d+\s*(emplois|offres)\s+(disponibles|trouvés)",
#     r"offres?\s+d'emploi\s+gratuit",
#     r"résultats?\s+de\s+recherche",
#     r"toutes?\s+les\s+offres",
#     r"^recherche\s+d'emploi$",
#     r"jobs?\s+(en\s+)?madagascar\s+jobs",  # "... madagascar jobs" (agrégateur)
#     r"liste\s+des\s+(offres|emplois)",
#     # --- Candidats / prestataires qui se vendent (PAS une opportunité
#     # pour ALTIORA — c'est l'inverse : quelqu'un cherche du travail) ---
#     r"seeking\s+work",
#     r"available\s+(immediately|now|for\s+work)",
#     r"disponible\s+(immédiatement|pour\s+mission|pour\s+freelance)",
#     r"à\s+la\s+recherche\s+d'un(e)?\s+(poste|mission|opportunité)",
#     r"je\s+(cherche|recherche)\s+(une\s+)?(mission|poste|opportunité)",
#     r"freelance\s+disponible",
#     r"open\s+to\s+work",
# ]

# # Pattern de profil personnel type LinkedIn : "Prénom I. - Titre"
# # (ex: "Jordana J. - Automation Specialist") — un individu qui se
# # présente, pas une organisation qui recrute.
# _PERSONAL_PROFILE_REGEX = re.compile(
#     r"^[A-ZÀ-Ý][a-zà-ÿ]+\s+[A-Z]\.\s*[-–|]",
# )

# _HARD_REJECT_REGEX = re.compile("|".join(HARD_REJECT_PATTERNS), re.IGNORECASE)


# def _is_hard_rejected(title: str, url: str) -> bool:
#     """Détection déterministe des pages agrégateurs/listes/profils personnels."""
#     title_stripped = title.strip()

#     if _PERSONAL_PROFILE_REGEX.match(title_stripped):
#         return True

#     return bool(_HARD_REJECT_REGEX.search(title)) or bool(
#         _HARD_REJECT_REGEX.search(url)
#     )


# def rank_results(
#     results: List[Dict[str, Any]],
#     query: str,
# ) -> List[Dict[str, Any]]:
#     """
#     Trie TOUS les résultats par score de pertinence heuristique
#     (sans troncature). Permet à l'appelant de traiter les résultats
#     par lots successifs (fallback si le 1er lot ne donne rien).
#     """

#     if not results:
#         return []

#     logger.info("🔧 PRÉFILTRAGE : %d résultats", len(results))

#     # ------------------------------------------------------------
#     # ÉTAPE 0 — REJET DUR (agrégateurs, listes génériques)
#     # Fait AVANT le classement : ces pages ne sont jamais des
#     # opportunités précises, autant les éliminer sans leur donner
#     # de score.
#     # ------------------------------------------------------------

#     survivors = []
#     for result in results:
#         if not isinstance(result, dict):
#             continue

#         title = str(result.get("title", ""))
#         url = str(result.get("url", ""))

#         if _is_hard_rejected(title, url):
#             logger.info("🚫 Rejet dur (agrégateur) : %s", title[:70])
#             continue

#         survivors.append(result)

#     logger.info(
#         "✅ Rejet dur : %d résultat(s) écarté(s), %d restant(s)",
#         len(results) - len(survivors),
#         len(survivors),
#     )

#     results = survivors

#     if not results:
#         return []

#     query_terms = [
#         word.lower()
#         for word in re.findall(r"[a-zA-ZÀ-ÿ0-9+#.-]+", query)
#         if len(word) >= 3
#     ]

#     relevant_terms = set(query_terms) | GENERIC_RELEVANT_TERMS

#     for result in results:
#         if not isinstance(result, dict):
#             continue

#         title = str(result.get("title", "")).lower()
#         content = str(
#             result.get("content", "") or result.get("snippet", "")
#         ).lower()
#         url = str(result.get("url", "")).lower()

#         score = 0

#         for term in relevant_terms:
#             if term in title:
#                 score += 3
#             elif term in content:
#                 score += 1

#         if ".mg" in url or "madagascar" in content or "antananarivo" in content:
#             score += 5

#         if any(term in content for term in ACTION_INDICATORS):
#             score += 3

#         if "asako" in url:
#             score += 3
#         if "portaljob" in url:
#             score += 2
#         if "linkedin" in url:
#             score += 2

#         result["prefilter_score"] = score

#     results.sort(key=lambda item: item.get("prefilter_score", 0), reverse=True)

#     logger.info("✅ PRÉFILTRAGE : %d résultats classés", len(results))

#     for r in results:
#         logger.info(
#             "   score=%d | %s",
#             r.get("prefilter_score", 0),
#             str(r.get("title", "?"))[:70],
#         )

#     return results


# def prefilter_results(
#     results: List[Dict[str, Any]],
#     query: str,
# ) -> List[Dict[str, Any]]:
#     """
#     Compatibilité : retourne uniquement les MAX_RESULTS_AI meilleurs
#     résultats (comportement d'origine, sans fallback par lots).
#     """
#     ranked = rank_results(results, query)
#     selected = ranked[:MAX_RESULTS_AI]

#     logger.info(
#         "✅ PRÉFILTRAGE : %d résultats gardés sur %d",
#         len(selected),
#         len(ranked),
#     )

#     return selected


# app/services/veille/prefilter_service.py
# ============================================================
# SERVICE PRÉFILTRAGE — Version propre et fonctionnelle
# ============================================================
# Règles :
#   - Rejette UNIQUEMENT le bruit évident (articles, profils)
#   - GARDE les agrégateurs (ils contiennent des offres)
#   - Bonus aux sources malgaches et aux agrégateurs reconnus
# ============================================================

import logging
import os
import re
from typing import Any
from collections import deque
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

MAX_RESULTS_AI = int(os.getenv("MAX_RESULTS_AI", "8"))

# ============================================================
# TERMES PERTINENTS (bonus au score)
# ============================================================
GENERIC_RELEVANT_TERMS = {
    "ia", "data", "n8n", "automatisation", "automation",
    "no-code", "low-code", "python", "react", "fastapi", "llm",
    "machine learning", "développeur", "developer", "developpeur",
    "cdi", "cdd", "stage", "freelance", "emploi", "recrutement",
    "offre", "job", "informatique", "digital", "tech",
}

ACTION_INDICATORS = {
    "cdi", "cdd", "stage", "freelance", "mission", "recrute",
    "recrutement", "postuler", "appel d'offres", "emploi",
    "offre", "job", "opportunité", "candidature",
}

# ============================================================
# REJET DUR — UNIQUEMENT le bruit évident
# ============================================================
# ⚠️ NE PAS rejeter les agrégateurs (Asako, PortalJob, etc.)
# ⚠️ Rejeter UNIQUEMENT : articles, tutoriels, profils personnels
HARD_REJECT_PATTERNS = [
    # Articles / tutoriels
    r"tutoriel\s+complet",
    r"guide\s+(complet|débutant)",
    r"apprenez\s+l",
    r"qu'est-ce\s+que\s+l",
    r"définition\s+de",
    r"^wikipedia",
    r"^youtube",
    # Profils personnels qui cherchent du travail (PAS une opportunité)
    r"seeking\s+work",
    r"available\s+(immediately|now|for\s+work)",
    r"disponible\s+(immédiatement|pour\s+mission|pour\s+freelance)",
    r"à\s+la\s+recherche\s+d'un(e)?\s+(poste|mission|opportunité)",
    r"je\s+(cherche|recherche)\s+(une\s+)?(mission|poste|opportunité)",
    r"freelance\s+disponible",
    r"open\s+to\s+work",
]

# Profil personnel type LinkedIn : "Prénom I. - Titre"
_PERSONAL_PROFILE_REGEX = re.compile(
    r"^[A-ZÀ-Ý][a-zà-ÿ]+\s+[A-Z]\.\s*[-–|]",
)

_HARD_REJECT_REGEX = re.compile("|".join(HARD_REJECT_PATTERNS), re.IGNORECASE)

# Pages sans valeur pour le LLM : listing vide, CV / profil candidat
_EMPTY_LISTING_REGEX = re.compile(
    r"\b0\s+offres?\s+d'emplois?\s+trouv|aucune\s+offre\s+(?:d'emploi\s+)?ne\s+correspond",
    re.IGNORECASE,
)
_CV_URL_REGEX = re.compile(r"/(?:cv|candidats?|profils?)(?:[/_-]|$)", re.IGNORECASE)

# Vocabulaire des marchés / consultations : c'est la cible de M1
TENDER_TERMS = (
    "appel d'offres", "appel d'offre", "avis d'appel", "manifestation d'intérêt",
    "manifestation d'interet", "termes de référence", "termes de reference",
    "dossier d'appel", "consultation", "sollicitation", "request for proposal",
    "expression of interest", "terms of reference",
)


# Avis de résultats / d'attribution : marché déjà attribué, trop tard pour y répondre.
# Expressions précises seulement ("résultats" seul apparaît dans tout TDR).
_AVIS_RESULTATS_REGEX = re.compile(
    r"avis\s+de\s+publication\s+de\s+r[ée]sultats?|publication\s+des\s+r[ée]sultats|"
    r"avis\s+d'attribution|attribution\s+(?:d[ée]finitive|provisoire)|"
    r"march[ée]\s+attribu[ée]|proc[èe]s[- ]verbal\s+d'ouverture|contract\s+award",
    re.IGNORECASE,
)

_TECH_TITLE = re.compile(
    r"\b(?:informatique|num[ée]rique|digital|web|pao|python|excel|data|devops|"
    r"cloud|cybers[ée]curit[ée]|bureautique|logiciel|r[ée]seau|ia|ict|it)\b|"
    r"intelligence artificielle|syst[èe]me.*information", re.IGNORECASE,
)
_FOREIGN_LOCATION = re.compile(
    r"\b(?:s[ée]n[ée]gal|burundi|egypt|egypte|[ée]gypte|b[ée]nin|douala|"
    r"cameroun|addis|[ée]thiopie|guin[ée]e|liban|maroc|boulogne-billancourt)\b", re.IGNORECASE,
)


def rejection_reason(result: dict[str, Any]) -> str | None:
    """Rejets prouvables ; une information manquante reste à analyser."""
    title = str(result.get("title", ""))
    content = str(result.get("content", "") or result.get("snippet", ""))
    text = f"{title} {content}"
    local = re.search(r"madagascar|malgache|malagasy|antananarivo|menabe", text, re.IGNORECASE)
    if _FOREIGN_LOCATION.search(title) and not local:
        return "localisation étrangère explicite"
    if not _TECH_TITLE.search(title) and re.search(
        r"kits solaires|gestion.*for[êe]ts|conservation.*biodiversit[ée]|"
        r"water resources|macro[ée]valuation|evaluability assessment|"
        r"impression des documents|^é?ditorial|croissance et r[ée]formes|"
        r"production.*tomate|transformation des produits|packaging|r[èe]gles d.origine.*cedeao|"
        r"restauration.*p[âa]tisserie|motorcycles|mat[ée]riels roulants",
        title, re.IGNORECASE,
    ):
        return "objet explicitement hors prestation informatique"
    # Une date de publication ancienne ne suffit pas à prouver l'expiration.
    deadline = result.get("deadline")
    if deadline:
        from datetime import date
        try:
            if date.fromisoformat(str(deadline)[:10]) < date.today():
                return "échéance explicite dépassée"
        except ValueError:
            pass
    return None


def navigation_reason(result):
    """Ces pages servent à découvrir des liens, pas à qualifier un marché."""
    parsed = urlparse(str(result.get("url") or ""))
    path = parsed.path.lower().rstrip("/")
    if "/blog/" in path or re.search(r"document d.enregistrement universel|^rapport annuel|^l.afrique en communs", str(result.get("title") or ""), re.I):
        return "Contenu informatif : aucune annonce individuelle de prestation identifiée"
    if (path in {"", "/appels-doffres", "/appels-a-manifestations-dinterets", "/emploi",
                 "/offres-emploi-aujourdhui", "/offres-emploi", "/offres-emploi-semaine"}
            or "/category/" in path or "/company/" in path
            or "adminshowbuyer" in path or path.endswith("list.do")
            or re.search(r"/emploi/(?:s-|m-|teletravail)|/jobs/search|/jobs/[^/]*emplois|/author/|/fr/recherche", path)):
        return "Page de navigation : retrouver une annonce individuelle avant l'analyse IA"
    return None


def _is_low_value(result: dict[str, Any]) -> bool:
    """Listing vide, page CV ou avis de résultats : jamais une opportunité."""
    title = str(result.get("title", ""))
    content = str(result.get("content", "") or result.get("snippet", ""))
    header = f"{title} {content[:500]}"
    if re.search(r"\bcancelled\b|\bannul[ée]\b|\bwithdrawn\b", header, re.IGNORECASE):
        return True
    if re.search(
        r"appels? d['’]offres? et passations de marchés|"
        r"^rapport\b|^r[ée]publique de madagascar$|"
        r"^madagascar\s*\|\s*afd",
        title.strip(),
        re.IGNORECASE,
    ):
        return True
    if _EMPTY_LISTING_REGEX.search(content):
        return True
    if _AVIS_RESULTATS_REGEX.search(f"{result.get('title', '')} {content[:400]}"):
        return True
    return bool(_CV_URL_REGEX.search(str(result.get("url", ""))))


def _dedupe(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Retire les doublons (même URL, ou même titre + même début de contenu)."""
    seen: set[str] = set()
    unique = []
    for result in results:
        url = str(result.get("url", "")).strip().lower().rstrip("/")
        content = str(result.get("content", "") or result.get("snippet", ""))
        signature = (
            str(result.get("title", "")).strip().lower()
            + "|" + re.sub(r"\s+", " ", content).strip().lower()
        )
        if (url and url in seen) or signature in seen:
            continue
        if url:
            seen.add(url)
        seen.add(signature)
        unique.append(result)
    return unique


def _is_hard_rejected(title: str, url: str) -> bool:
    """
    Détection déterministe — UNIQUEMENT pour :
      - articles/tutoriels
      - profils personnels (LinkedIn "Nom I. - Titre")
    NE rejette PAS les agrégateurs.
    """
    title_stripped = (title or "").strip()

    # Profil personnel
    if _PERSONAL_PROFILE_REGEX.match(title_stripped):
        return True

    # Articles/tutoriels
    if _HARD_REJECT_REGEX.search(title_stripped):
        return True
    if _HARD_REJECT_REGEX.search(url or ""):
        return True

    return False


def rank_results(
    results: list[dict[str, Any]],
    query: str,
) -> list[dict[str, Any]]:
    """
    Trie TOUS les résultats par score de pertinence heuristique.
    Garde les agrégateurs, rejette uniquement le bruit évident.
    """

    if not results:
        return []

    logger.info("🔧 PRÉFILTRAGE : %d résultats", len(results))

    # ------------------------------------------------------------
    # ÉTAPE 0 — REJET DUR (UNIQUEMENT articles/profils)
    # ------------------------------------------------------------
    survivors = []
    for result in results:
        if not isinstance(result, dict):
            continue

        title = str(result.get("title", ""))
        url = str(result.get("url", ""))

        reason = rejection_reason(result)
        if reason:
            logger.info("🚫 Préfiltre : %s — %s", reason, title[:70])
            continue

        if _is_hard_rejected(title, url):
            logger.info("🚫 Rejet dur (article/profil) : %s", title[:70])
            continue

        if _is_low_value(result):
            logger.info("🚫 Rejet dur (listing vide / CV / résultats) : %s", title[:70])
            continue

        survivors.append(result)

    nb_avant_dedup = len(survivors)
    survivors = _dedupe(survivors)

    logger.info(
        "✅ Rejet dur : %d résultat(s) écarté(s) dont %d doublon(s), %d restant(s)",
        len(results) - len(survivors),
        nb_avant_dedup - len(survivors),
        len(survivors),
    )

    results = survivors

    if not results:
        return []

    # ------------------------------------------------------------
    # ÉTAPE 1 — SCORING HEURISTIQUE
    # ------------------------------------------------------------
    query_terms = [
        word.lower()
        for word in re.findall(r"[a-zA-ZÀ-ÿ0-9+#.-]+", query)
        if len(word) >= 3
    ]

    relevant_terms = set(query_terms) | GENERIC_RELEVANT_TERMS

    for result in results:
        if not isinstance(result, dict):
            continue

        title = str(result.get("title", "")).lower()
        content = str(
            result.get("content", "") or result.get("snippet", "")
        ).lower()
        url = str(result.get("url", "")).lower()

        score = 0

        # Score par termes pertinents
        for term in relevant_terms:
            if term in title:
                score += 3
            elif term in content:
                score += 1

        # Bonus Madagascar
        if ".mg" in url or "madagascar" in content or "antananarivo" in content:
            score += 5

        # Bonus action (recrute, CDI, stage, etc.)
        if any(term in content for term in ACTION_INDICATORS):
            score += 3

        # Bonus marché / consultation (cible principale de M1)
        if any(term in title or term in content for term in TENDER_TERMS):
            score += 8

        # ✅ Bonus AGRÉGATEURS reconnus (ils contiennent des offres)
        if "asako" in url:
            score += 5
        if "portaljob" in url:
            score += 4
        if "job2mada" in url:
            score += 4
        if "linkedin" in url:
            score += 3
        if "codeko" in url:
            score += 3
        if "optioncarriere" in url:
            score += 2
        if "indeed" in url:
            score += 2

        result["prefilter_score"] = score
        if result.get("source_preferred"):
            result["prefilter_score"] += 4
        # Une annonce individuelle doit passer avant sa page de catégorie,
        # même si cette dernière répète davantage de mots de la requête.
        path = urlparse(str(result.get("url", ""))).path.lower()
        if path.rstrip("/") in {"/appels-doffres", "/appels-a-manifestations-dinterets"} or any(
            p in path for p in ("/category/", "adminshowbuyer", "/tenders/list.do")
        ):
            result["prefilter_score"] -= 20
        elif re.search(r"intelligence-artificielle|analyse-de-donnees|formation-informatique|devops|bureautique|cybersecurite", path):
            result["prefilter_score"] += 12

    # ------------------------------------------------------------
    # ÉTAPE 2 — TRI
    # ------------------------------------------------------------
    results.sort(key=lambda item: item.get("prefilter_score", 0), reverse=True)

    logger.info("✅ PRÉFILTRAGE : %d résultats classés", len(results))

    for r in results[:10]:
        logger.info(
            "   score=%d | %s",
            r.get("prefilter_score", 0),
            str(r.get("title", "?"))[:70],
        )

    return results


def source_domain(url: str) -> str:
    """Domaine de provenance ; regroupe www et les portails dgMarket."""
    hostname = (urlparse(url).hostname or "inconnu").lower().removeprefix("www.")
    if hostname == "dgmarket.com" or hostname.endswith(".dgmarket.com"):
        return "dgmarket.com"
    return hostname


def diversify_sources(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Alterne les domaines en conservant le classement dans chaque domaine.

    Cette sélection porte sur les pages déjà collectées ; elle ne prouve pas
    qu'un site a répondu directement et n'ajoute aucun appel réseau.
    """
    groups: dict[str, deque] = {}
    for result in results:
        groups.setdefault(source_domain(str(result.get("url", ""))), deque()).append(result)
    selected = []
    while groups:
        for domain in list(groups):
            selected.append(groups[domain].popleft())
            if not groups[domain]:
                del groups[domain]
    return selected


def prefilter_results(
    results: list[dict[str, Any]],
    query: str,
) -> list[dict[str, Any]]:
    """Compatibilité : retourne uniquement les MAX_RESULTS_AI meilleurs."""
    ranked = rank_results(results, query)
    selected = ranked[:MAX_RESULTS_AI]

    logger.info(
        "✅ PRÉFILTRAGE : %d résultats gardés sur %d",
        len(selected),
        len(ranked),
    )

    return selected
