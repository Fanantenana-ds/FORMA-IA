# # app/services/veille/validation_service.py
# # ============================================================
# # SERVICE VALIDATION — filtre anti-faux-positifs + normalisation
# # ============================================================
# # Applique les règles de qualité de veille.yaml (ÉTAPE 4/12),
# # normalise les champs, déduplique, et valide la forme finale
# # via le schéma Pydantic partagé (app.schemas.veille).
# # ============================================================

# import logging
# import re
# from typing import Any, Dict, List, Optional

# from pydantic import ValidationError

# from app.schemas.veille import OpportunityResult
# from app.utils.url_utils import normalize_url

# logger = logging.getLogger(__name__)

# REJECTED_TYPES = {
#     "article", "information", "guide", "tutoriel", "étude",
#     "rapport", "publicité", "promotion", "autre contenu non actionnable",
# }

# GENERIC_AGGREGATOR_TITLES = [
#     "offres d'emploi digital et tech", "offres d'emploi gratuit",
#     "offres d'emploi à madagascar", "emplois développeur",
#     "jobs en madagascar", "résultats de recherche",
#     "recherche d'emploi", "search jobs", "job search",
# ]

# ACTION_WORDS = [
#     "recrute", "recrutement", "recherche", "poste", "mission",
#     "prestataire", "consultant", "formation", "appel d'offres",
#     "appel offres", "cdi", "cdd", "stage", "freelance",
#     "postuler", "candidature",
# ]

# TYPES_REQUIRING_ORGANIZER = {
#     "emploi", "appel_offres", "prestation", "formation", "projet", "stage",
# }


# def quality_filter(opportunity: Dict[str, Any]) -> bool:
#     """Filtre anti-faux-positifs — cf. veille.yaml ÉTAPE 4/12."""

#     title = str(opportunity.get("title", "")).strip()
#     summary = str(opportunity.get("summary", "") or "").strip()
#     organizer = str(opportunity.get("organizer", "") or "").strip()
#     opportunity_type = str(opportunity.get("opportunity_type", "") or "").lower()
#     confidence = opportunity.get("confidence", 0)

#     if not title or not summary:
#         return False

#     try:
#         confidence_value = float(confidence)
#     except (TypeError, ValueError):
#         confidence_value = 0

#     if confidence_value < 0.50:
#         logger.info("🚫 Rejet confidence faible : %s", title)
#         return False

#     if opportunity_type in REJECTED_TYPES:
#         logger.info("🚫 Rejet type non actionnable : %s", title)
#         return False

#     title_lower = title.lower()
#     if any(pattern in title_lower for pattern in GENERIC_AGGREGATOR_TITLES):
#         logger.info("🚫 Rejet agrégateur : %s", title)
#         return False

#     if not any(
#         word in f"{title_lower} {summary.lower()}" for word in ACTION_WORDS
#     ):
#         logger.info("🚫 Aucun indice d'action concrète : %s", title)
#         return False

#     if not organizer and opportunity_type in TYPES_REQUIRING_ORGANIZER:
#         logger.info("🚫 Organisation non identifiée : %s", title)
#         return False

#     return True


# def normalize_opportunity(opportunity: Dict[str, Any]) -> Optional[Dict[str, Any]]:
#     """Normalise les champs et rejette si is_actionable n'est pas True."""

#     if not isinstance(opportunity, dict):
#         return None

#     cleaned = dict(opportunity)
#     cleaned["url"] = normalize_url(cleaned.get("url", ""))

#     cleaned.setdefault("budget", "Non précisé")
#     cleaned.setdefault("deadline", None)
#     cleaned.setdefault("organizer", None)
#     cleaned.setdefault("source", None)
#     cleaned.setdefault("source_site", None)
#     cleaned.setdefault("source_priority", None)
#     cleaned.setdefault("domain", "autre")
#     cleaned.setdefault("opportunity_type", "autre")
#     cleaned.setdefault("flags", [])

#     if cleaned.get("is_actionable") is not True:
#         return None

#     try:
#         cleaned["confidence"] = float(cleaned.get("confidence", 0))
#     except (TypeError, ValueError):
#         cleaned["confidence"] = 0.0

#     try:
#         cleaned["score"] = int(float(cleaned.get("score", 0)))
#     except (TypeError, ValueError):
#         cleaned["score"] = 0

#     return cleaned


# def deduplicate(opportunities: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
#     """Déduplication par URL puis par titre normalisé."""

#     seen_urls = set()
#     seen_titles = set()
#     unique = []

#     for opportunity in opportunities:
#         url = str(opportunity.get("url", "")).strip().lower()
#         title = re.sub(
#             r"\s+", " ", str(opportunity.get("title", "")).strip().lower()
#         )

#         if url and url in seen_urls:
#             continue
#         if title and title in seen_titles:
#             continue

#         if url:
#             seen_urls.add(url)
#         if title:
#             seen_titles.add(title)

#         unique.append(opportunity)

#     return unique


# def validate_against_schema(opportunity: Dict[str, Any]) -> Optional[Dict[str, Any]]:
#     """
#     Valide la forme finale via le schéma Pydantic partagé
#     (app.schemas.veille.OpportunityResult) — c'est ce schéma qui
#     sera consommé par le Backend / Frontend.
#     """
#     try:
#         validated = OpportunityResult(**opportunity)
#         return validated.model_dump()
#     except ValidationError as exc:
#         logger.warning(
#             "🚫 Rejet validation Pydantic : %s — %s",
#             opportunity.get("title", "?"),
#             exc,
#         )
#         return None


# def fallback_response(results: List[Dict[str, Any]]) -> Dict[str, Any]:
#     """
#     Réponse de repli stricte : aucun résultat Tavily brut n'est
#     transformé automatiquement en opportunité en cas d'échec Groq.
#     """
#     logger.warning("⚠️ FALLBACK M1 : zéro opportunité pour éviter les faux positifs")

#     return {
#         "opportunities": [],
#         "market_signals": [],
#         "total": 0,
#         "notes": (
#             "Analyse IA indisponible. Aucune opportunité brute "
#             "n'est promue automatiquement."
#         ),
#         "status": "degraded",
#         "ai_provider": "fallback",
#         "statistics": {
#             "raw_results": len(results),
#             "filtered": len(results),
#             "groq_results": 0,
#             "final": 0,
#             "madagascar": 0,
#             "processing_time_seconds": 0,
#         },
#     }





# # app/services/veille/validation_service.py
# # ============================================================
# # SERVICE VALIDATION — filtre anti-faux-positifs + normalisation
# # ============================================================
# # Applique les règles de qualité de veille.yaml (ÉTAPE 4/12),
# # normalise les champs, déduplique, et valide la forme finale
# # via le schéma Pydantic partagé (app.schemas.veille).
# # ============================================================

# import logging
# import re
# from typing import Any, Dict, List, Optional

# from pydantic import ValidationError

# from app.schemas.veille import OpportunityResult
# from app.utils.url_utils import normalize_url

# logger = logging.getLogger(__name__)

# REJECTED_TYPES = {
#     "article", "information", "guide", "tutoriel", "étude",
#     "rapport", "publicité", "promotion", "autre contenu non actionnable",
# }

# GENERIC_AGGREGATOR_TITLES = [
#     "offres d'emploi digital et tech", "offres d'emploi gratuit",
#     "offres d'emploi à madagascar", "emplois développeur",
#     "jobs en madagascar", "résultats de recherche",
#     "recherche d'emploi", "search jobs", "job search",
# ]

# ACTION_WORDS = [
#     "recrute", "recrutement", "recherche", "poste", "mission",
#     "prestataire", "consultant", "formation", "appel d'offres",
#     "appel offres", "cdi", "cdd", "stage", "freelance",
#     "postuler", "candidature",
# ]

# TYPES_REQUIRING_ORGANIZER = {
#     "emploi", "appel_offres", "prestation", "formation", "projet", "stage",
# }

# # Plateformes connues qui hébergent des offres sans être elles-mêmes
# # l'employeur. Si "organizer" == "source" ET que "source" ressemble
# # à une de ces plateformes, c'est un signal que le LLM a probablement
# # confondu l'hébergeur avec le véritable recruteur (cf. diagnostic :
# # distinction source/organizer pas fiable).
# KNOWN_PLATFORMS = {
#     "linkedin", "facebook", "indeed", "glassdoor", "freelancer",
#     "upwork", "workmada", "asako", "asako.mg", "portaljob",
#     "portailjob", "emploi.mg", "jobmada",
# }


# def _flag_ambiguous_organizer(opportunity: Dict[str, Any]) -> None:
#     """
#     Ajoute le flag 'organizer_unclear' si source et organizer sont
#     identiques et correspondent à une plateforme connue plutôt qu'à
#     une vraie entreprise. Ne rejette PAS l'opportunité — c'est un
#     signal pour la revue humaine, pas une preuve d'erreur.
#     """
#     source = str(opportunity.get("source", "") or "").strip().lower()
#     organizer = str(opportunity.get("organizer", "") or "").strip().lower()
#     source_site = str(opportunity.get("source_site", "") or "").strip().lower()

#     if not source or not organizer:
#         return

#     looks_like_platform = any(
#         platform in source or platform in source_site
#         for platform in KNOWN_PLATFORMS
#     )

#     if source == organizer and looks_like_platform:
#         flags = opportunity.get("flags", [])
#         if "organizer_unclear" not in flags:
#             flags.append("organizer_unclear")
#         opportunity["flags"] = flags
#         logger.info(
#             "⚠️ organizer_unclear : source et organizer identiques "
#             "('%s'), probable confusion plateforme/employeur",
#             source,
#         )


# def quality_filter(opportunity: Dict[str, Any]) -> bool:
#     """Filtre anti-faux-positifs — cf. veille.yaml ÉTAPE 4/12."""

#     title = str(opportunity.get("title", "")).strip()
#     summary = str(opportunity.get("summary", "") or "").strip()
#     organizer = str(opportunity.get("organizer", "") or "").strip()
#     opportunity_type = str(opportunity.get("opportunity_type", "") or "").lower()
#     confidence = opportunity.get("confidence", 0)

#     if not title or not summary:
#         return False

#     try:
#         confidence_value = float(confidence)
#     except (TypeError, ValueError):
#         confidence_value = 0

#     if confidence_value < 0.50:
#         logger.info("🚫 Rejet confidence faible : %s", title)
#         return False

#     if opportunity_type in REJECTED_TYPES:
#         logger.info("🚫 Rejet type non actionnable : %s", title)
#         return False

#     title_lower = title.lower()
#     if any(pattern in title_lower for pattern in GENERIC_AGGREGATOR_TITLES):
#         logger.info("🚫 Rejet agrégateur : %s", title)
#         return False

#     if not any(
#         word in f"{title_lower} {summary.lower()}" for word in ACTION_WORDS
#     ):
#         logger.info("🚫 Aucun indice d'action concrète : %s", title)
#         return False

#     if not organizer and opportunity_type in TYPES_REQUIRING_ORGANIZER:
#         logger.info("🚫 Organisation non identifiée : %s", title)
#         return False

#     return True


# def normalize_opportunity(opportunity: Dict[str, Any]) -> Optional[Dict[str, Any]]:
#     """Normalise les champs et rejette si is_actionable n'est pas True."""

#     if not isinstance(opportunity, dict):
#         return None

#     cleaned = dict(opportunity)
#     cleaned["url"] = normalize_url(cleaned.get("url", ""))

#     cleaned.setdefault("budget", "Non précisé")
#     cleaned.setdefault("deadline", None)
#     cleaned.setdefault("organizer", None)
#     cleaned.setdefault("source", None)
#     cleaned.setdefault("source_site", None)
#     cleaned.setdefault("source_priority", None)
#     cleaned.setdefault("domain", "autre")
#     cleaned.setdefault("opportunity_type", "autre")
#     cleaned.setdefault("flags", [])

#     if cleaned.get("is_actionable") is not True:
#         return None

#     try:
#         cleaned["confidence"] = float(cleaned.get("confidence", 0))
#     except (TypeError, ValueError):
#         cleaned["confidence"] = 0.0

#     try:
#         cleaned["score"] = int(float(cleaned.get("score", 0)))
#     except (TypeError, ValueError):
#         cleaned["score"] = 0

#     _flag_ambiguous_organizer(cleaned)

#     return cleaned


# def deduplicate(opportunities: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
#     """Déduplication par URL puis par titre normalisé."""

#     seen_urls = set()
#     seen_titles = set()
#     unique = []

#     for opportunity in opportunities:
#         url = str(opportunity.get("url", "")).strip().lower()
#         title = re.sub(
#             r"\s+", " ", str(opportunity.get("title", "")).strip().lower()
#         )

#         if url and url in seen_urls:
#             continue
#         if title and title in seen_titles:
#             continue

#         if url:
#             seen_urls.add(url)
#         if title:
#             seen_titles.add(title)

#         unique.append(opportunity)

#     return unique


# def validate_against_schema(opportunity: Dict[str, Any]) -> Optional[Dict[str, Any]]:
#     """
#     Valide la forme finale via le schéma Pydantic partagé
#     (app.schemas.veille.OpportunityResult) — c'est ce schéma qui
#     sera consommé par le Backend / Frontend.
#     """
#     try:
#         validated = OpportunityResult(**opportunity)
#         return validated.model_dump()
#     except ValidationError as exc:
#         logger.warning(
#             "🚫 Rejet validation Pydantic : %s — %s",
#             opportunity.get("title", "?"),
#             exc,
#         )
#         return None


# def fallback_response(results: List[Dict[str, Any]]) -> Dict[str, Any]:
#     """
#     Réponse de repli stricte : aucun résultat Tavily brut n'est
#     transformé automatiquement en opportunité en cas d'échec Groq.
#     """
#     logger.warning("⚠️ FALLBACK M1 : zéro opportunité pour éviter les faux positifs")

#     return {
#         "opportunities": [],
#         "market_signals": [],
#         "total": 0,
#         "notes": (
#             "Analyse IA indisponible. Aucune opportunité brute "
#             "n'est promue automatiquement."
#         ),
#         "status": "degraded",
#         "ai_provider": "fallback",
#         "statistics": {
#             "raw_results": len(results),
#             "filtered": len(results),
#             "groq_results": 0,
#             "final": 0,
#             "madagascar": 0,
#             "processing_time_seconds": 0,
#         },
#     }







# app/services/veille/validation_service.py
# ============================================================
# SERVICE VALIDATION — filtre anti-faux-positifs + normalisation
# ============================================================
# Applique les règles de qualité de veille.yaml (ÉTAPE 4/12),
# normalise les champs, déduplique, et valide la forme finale
# via le schéma Pydantic partagé (app.schemas.veille).
# ============================================================

import logging
import re
from typing import Any, Dict, List, Optional

from pydantic import ValidationError

from app.schemas.veille import OpportunityResult
from app.utils.url_utils import normalize_url

logger = logging.getLogger(__name__)

REJECTED_TYPES = {
    "article", "information", "guide", "tutoriel", "étude",
    "rapport", "publicité", "promotion", "autre contenu non actionnable",
}

GENERIC_AGGREGATOR_TITLES = [
    "offres d'emploi digital et tech", "offres d'emploi gratuit",
    "offres d'emploi à madagascar", "emplois développeur",
    "jobs en madagascar", "résultats de recherche",
    "recherche d'emploi", "search jobs", "job search",
]

# ✅ FANITSIA 1 : Ampitomboy ny ACTION_WORDS
ACTION_WORDS = [
    "recrute", "recrutement", "recherche", "poste", "mission",
    "prestataire", "consultant", "formation", "appel d'offres",
    "appel offres", "cdi", "cdd", "stage", "freelance",
    "postuler", "candidature",
    "hiring", "recruit", "recherchons", "offre", "opportunité",
    "cherchons", "rejoignez", "rejoindre", "postulez",
    "développeur", "developpeur", "fullstack", "full stack",
    "devops", "ia", "intelligence artificielle", "data scientist",
    "expert", "ingénieur", "ingenieur", "stagiaire", "alternance",
    "data", "scientist", "analyste", "analytics", "machine learning",
    "ml", "deep learning", "dl", "nlp", "computer vision",
]

TYPES_REQUIRING_ORGANIZER = {
    "emploi", "appel_offres", "prestation", "formation", "projet", "stage",
}

# ✅ FANITSIA 2 : Esory ny "central test", "novity madagascar", "astek madagascar"
KNOWN_PLATFORMS = {
    "linkedin", "facebook", "indeed", "glassdoor", "freelancer",
    "upwork", "workmada", "asako", "asako.mg", "portaljob",
    "portailjob", "emploi.mg", "jobmada",
}


def _flag_ambiguous_organizer(opportunity: Dict[str, Any]) -> None:
    """
    Ajoute le flag 'organizer_unclear' si source et organizer sont
    identiques et correspondent à une plateforme connue plutôt qu'à
    une vraie entreprise. Ne rejette PAS l'opportunité — c'est un
    signal pour la revue humaine, pas une preuve d'erreur.
    """
    source = str(opportunity.get("source", "") or "").strip().lower()
    organizer = str(opportunity.get("organizer", "") or "").strip().lower()
    source_site = str(opportunity.get("source_site", "") or "").strip().lower()
    title = str(opportunity.get("title", "") or "").strip().lower()

    if not source or not organizer:
        return

    # ✅ FANITSIA 3 : Raha misy ny anaran'ny orinasa ao amin'ny lohateny na source,
    # dia aza atao hoe organizer_unclear
    organizer_clean = re.sub(r'[^a-z0-9]', '', organizer)
    title_clean = re.sub(r'[^a-z0-9]', '', title)
    source_clean = re.sub(r'[^a-z0-9]', '', source)
    
    if organizer_clean in title_clean or organizer_clean in source_clean:
        return

    # ✅ FANITSIA 3bis : Raha tsy misy indrindra ny "jobs", "emploi", "recrutement" ao amin'ny source,
    # dia avela handalo
    if "jobs" not in source and "emploi" not in source and "recrutement" not in source:
        return

    looks_like_platform = any(
        platform in source or platform in source_site
        for platform in KNOWN_PLATFORMS
    )

    if source == organizer and looks_like_platform:
        flags = opportunity.get("flags", [])
        if "organizer_unclear" not in flags:
            flags.append("organizer_unclear")
        opportunity["flags"] = flags
        logger.info(
            "⚠️ organizer_unclear : source et organizer identiques "
            "('%s'), probable confusion plateforme/employeur",
            source,
        )


def quality_filter(opportunity: Dict[str, Any]) -> bool:
    """Filtre anti-faux-positifs — cf. veille.yaml ÉTAPE 4/12."""

    title = str(opportunity.get("title", "")).strip()
    summary = str(opportunity.get("summary", "") or "").strip()
    organizer = str(opportunity.get("organizer", "") or "").strip()
    opportunity_type = str(opportunity.get("opportunity_type", "") or "").lower()
    confidence = opportunity.get("confidence", 0)

    if not title or not summary:
        return False

    try:
        confidence_value = float(confidence)
    except (TypeError, ValueError):
        confidence_value = 0

    # ✅ FANITSIA 4 : Ahena avy amin'ny 0.40 ho 0.35
    if confidence_value < 0.35:
        logger.info("🚫 Rejet confidence faible : %s", title)
        return False

    if opportunity_type in REJECTED_TYPES:
        logger.info("🚫 Rejet type non actionnable : %s", title)
        return False

    title_lower = title.lower()
    if any(pattern in title_lower for pattern in GENERIC_AGGREGATOR_TITLES):
        logger.info("🚫 Rejet agrégateur : %s", title)
        return False

    # ✅ FANITSIA 5 : Raha misy "data" na "scientist" dia avela handalo
    has_action = any(
        word in f"{title_lower} {summary.lower()}" for word in ACTION_WORDS
    )
    has_data_keyword = "data" in title_lower or "scientist" in title_lower or "analytics" in title_lower

    if not has_action and not has_data_keyword:
        logger.info("🚫 Aucun indice d'action concrète : %s", title)
        return False
    elif not has_action and has_data_keyword:
        logger.info("ℹ️ Action word faible mais accepté (data/science) : %s", title)

    if not organizer and opportunity_type in TYPES_REQUIRING_ORGANIZER:
        logger.info("🚫 Organisation non identifiée : %s", title)
        return False

    return True


def normalize_opportunity(opportunity: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Normalise les champs et rejette si is_actionable n'est pas True."""

    if not isinstance(opportunity, dict):
        return None

    cleaned = dict(opportunity)
    cleaned["url"] = normalize_url(cleaned.get("url", ""))

    cleaned.setdefault("budget", "Non précisé")
    cleaned.setdefault("deadline", None)
    cleaned.setdefault("organizer", None)
    cleaned.setdefault("source", None)
    cleaned.setdefault("source_site", None)
    cleaned.setdefault("source_priority", None)
    cleaned.setdefault("domain", "autre")
    cleaned.setdefault("opportunity_type", "autre")
    cleaned.setdefault("flags", [])

    if cleaned.get("is_actionable") is not True:
        return None

    try:
        cleaned["confidence"] = float(cleaned.get("confidence", 0))
    except (TypeError, ValueError):
        cleaned["confidence"] = 0.0

    try:
        cleaned["score"] = int(float(cleaned.get("score", 0)))
    except (TypeError, ValueError):
        cleaned["score"] = 0

    _flag_ambiguous_organizer(cleaned)

    return cleaned


def deduplicate(opportunities: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Déduplication par URL puis par titre normalisé."""

    seen_urls = set()
    seen_titles = set()
    unique = []

    for opportunity in opportunities:
        url = str(opportunity.get("url", "")).strip().lower()
        title = re.sub(
            r"\s+", " ", str(opportunity.get("title", "")).strip().lower()
        )

        if url and url in seen_urls:
            continue
        if title and title in seen_titles:
            continue

        if url:
            seen_urls.add(url)
        if title:
            seen_titles.add(title)

        unique.append(opportunity)

    return unique


def validate_against_schema(opportunity: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Valide la forme finale via le schéma Pydantic partagé
    (app.schemas.veille.OpportunityResult) — c'est ce schéma qui
    sera consommé par le Backend / Frontend.
    """
    try:
        validated = OpportunityResult(**opportunity)
        return validated.model_dump()
    except ValidationError as exc:
        logger.warning(
            "🚫 Rejet validation Pydantic : %s — %s",
            opportunity.get("title", "?"),
            exc,
        )
        return None


def fallback_response(results: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Réponse de repli stricte : aucun résultat Tavily brut n'est
    transformé automatiquement en opportunité en cas d'échec Groq.
    """
    logger.warning("⚠️ FALLBACK M1 : zéro opportunité pour éviter les faux positifs")

    return {
        "opportunities": [],
        "market_signals": [],
        "total": 0,
        "notes": (
            "Analyse IA indisponible. Aucune opportunité brute "
            "n'est promue automatiquement."
        ),
        "status": "degraded",
        "ai_provider": "fallback",
        "statistics": {
            "raw_results": len(results),
            "filtered": len(results),
            "groq_results": 0,
            "final": 0,
            "madagascar": 0,
            "processing_time_seconds": 0,
        },
    }