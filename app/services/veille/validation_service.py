# app/services/veille/validation_service.py
# ============================================================
# SERVICE VALIDATION — filtre anti-faux-positifs + normalisation
# ============================================================
# Version : V5.0 — Logs détaillés pour diagnostic recall
# ============================================================

import logging
import re
from typing import Any, Dict, List, Optional

from pydantic import ValidationError

from app.schemas.veille import OpportunityResult
from app.utils.url_utils import normalize_url

logger = logging.getLogger(__name__)


# ============================================================
# CONSTANTES
# ============================================================

REJECTED_TYPES = {
    "article", "information", "guide", "tutoriel", "étude",
    "rapport", "publicité", "promotion", "autre contenu non actionnable",
}

GENERIC_AGGREGATOR_TITLES = [
    "offres d'emploi gratuit",
    "jobs en madagascar", "résultats de recherche",
    "recherche d'emploi", "search jobs", "job search",
]

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
    "bureautique", "bureau", "tableau de bord", "dashboard",
    "cicd", "ci/cd", "git", "docker", "kubernetes",
    "cloud", "aws", "azure", "gcp",
]

TYPES_REQUIRING_ORGANIZER = {
    "emploi", "appel_offres", "prestation", "formation", "projet", "stage",
}

KNOWN_PLATFORMS = {
    "linkedin", "facebook", "indeed", "glassdoor", "freelancer",
    "upwork", "workmada", "asako", "asako.mg", "portaljob",
    "portailjob", "emploi.mg", "jobmada", "job2mada",
    "codeko", "optioncarriere",
}


# ============================================================
# EXTRACTION EMPLOYEUR DEPUIS URL
# ============================================================

_JOB_KEYWORDS_END = (
    r"data-analyst|analyste-data|data-scientist|scientist|"
    r"data-expert|data-engineer|"
    r"developer|developpeur|fullstack|full-stack|"
    r"expert|engineer|ingénieur|ingenieur|"
    r"technicien|consultant|"
    r"assistant|commercial|marketing|communication|"
    r"officer|lead|senior|junior|"
    r"stage|stagiaire|alternance|"
    r"cdi|cdd|freelance|recrutement|"
    r"offre|poste|job|"
    r"vba|powerbi|sql|web|frontend|backend|"
    r"devops|cloud|mobile|"
    r"php|java|python|react|laravel|symfony|wordpress|"
    r"angular|magento|net|vue|node"
)

_JOB_KEYWORDS_END_REGEX = re.compile(
    rf"-(?:{_JOB_KEYWORDS_END})(?:-(?:{_JOB_KEYWORDS_END}))*$",
    re.IGNORECASE,
)


def _extract_employer_from_url(url: str) -> Optional[str]:
    """Extrait le nom de l'employeur depuis l'URL d'une offre."""
    if not url:
        return None

    url_lower = url.lower()

    patterns = [
        r"portaljob-madagascar\.com/emploi/view/([a-z0-9-]+)",
        r"job2mada\.com/jobs/([a-z0-9-]+)",
        r"codeko\.tech/jobs?/([a-z0-9-]+)",
        r"asako\.mg/annonces/\d+-([a-z0-9-]+)",
    ]

    for pattern in patterns:
        match = re.search(pattern, url_lower)
        if not match:
            continue

        slug = match.group(1)
        slug = re.sub(r"[a-z]?\d+$", "", slug)

        previous = None
        while previous != slug:
            previous = slug
            slug = _JOB_KEYWORDS_END_REGEX.sub("", slug)

        slug = slug.strip("-")

        if not slug or len(slug) < 3:
            continue

        employer = " ".join(
            word.capitalize()
            for word in slug.split("-")
            if word and len(word) > 1
        )

        if len(employer) < 3:
            continue

        logger.info(
            "   ✅ Employeur extrait de l'URL : '%s' → '%s'",
            slug, employer
        )
        return employer

    return None


# ============================================================
# FLAG ORGANIZER AMBIGU
# ============================================================

def _flag_ambiguous_organizer(opportunity: Dict[str, Any]) -> None:
    """Ajoute le flag 'organizer_unclear' si source == organizer."""
    source = str(opportunity.get("source", "") or "").strip().lower()
    organizer = str(opportunity.get("organizer", "") or "").strip().lower()
    source_site = str(opportunity.get("source_site", "") or "").strip().lower()
    title = str(opportunity.get("title", "") or "").strip().lower()

    if not source or not organizer:
        return

    organizer_clean = re.sub(r'[^a-z0-9]', '', organizer)
    title_clean = re.sub(r'[^a-z0-9]', '', title)

    if organizer_clean in title_clean:
        return

    if "hiring" in source or "recrute" in source:
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


# ============================================================
# QUALITY FILTER — AVEC LOGS DÉTAILLÉS
# ============================================================

def quality_filter(opportunity: Dict[str, Any]) -> bool:
    """Filtre anti-faux-positifs — AVEC LOGS DÉTAILLÉS."""
    title = str(opportunity.get("title", "")).strip()
    summary = str(opportunity.get("summary", "") or "").strip()
    organizer = str(opportunity.get("organizer", "") or "").strip()
    opportunity_type = str(opportunity.get("opportunity_type", "") or "").lower()
    url = str(opportunity.get("url", "")).lower()
    confidence = opportunity.get("confidence", 0)

    # LOG 1 : title/summary vide
    if not title or not summary:
        logger.info(
            "      🚫 quality_filter REJET: title/summary vide | "
            "title='%s' | summary_len=%d",
            title[:40] if title else "(vide)",
            len(summary)
        )
        return False

    # LOG 2 : confidence faible
    try:
        confidence_value = float(confidence)
    except (TypeError, ValueError):
        confidence_value = 0

    if confidence_value < 0.25:
        logger.info(
            "      🚫 quality_filter REJET: confidence faible (%.2f < 0.25)",
            confidence_value
        )
        return False

    # LOG 3 : type rejeté
    if opportunity_type in REJECTED_TYPES:
        logger.info(
            "      🚫 quality_filter REJET: type non actionnable (%s)",
            opportunity_type
        )
        return False

    # LOG 4 : URL listing
    listing_url_patterns = [
        "/emploi/liste", "/emploi/secteur", "/emploi/page",
        "/jobs/list", "/jobs/search", "/emploi/categorie",
        "/offres/liste", "?page=", "/page/1", "/page/2",
    ]
    if any(p in url for p in listing_url_patterns):
        logger.info(
            "      🚫 quality_filter REJET: URL = page de listing (%s)",
            url[:70]
        )
        return False

    # LOG 5 : titre générique
    title_lower = title.lower()
    generic_titles = [
        "offres d'emploi", "emplois disponibles", "offres disponibles",
        "liste des offres", "toutes les offres", "jobs in",
        "emploi it", "emploi informatique",
    ]
    if any(g in title_lower for g in generic_titles):
        logger.info(
            "      🚫 quality_filter REJET: titre générique ('%s')",
            title[:60]
        )
        return False

    # LOG 6 : agrégateur
    is_aggregator = any(
        pattern in title_lower for pattern in GENERIC_AGGREGATOR_TITLES
    )
    if is_aggregator:
        logger.info(
            "      🚫 quality_filter REJET: agrégateur ('%s')",
            title[:60]
        )
        return False

    # LOG 7 : pas d'action word
    has_action = any(
        word in f"{title_lower} {summary.lower()}" for word in ACTION_WORDS
    )
    if not has_action:
        logger.info(
            "      🚫 quality_filter REJET: aucun mot-clé d'action | title='%s'",
            title[:60]
        )
        return False

    # LOG 8 : pas d'organizer
    if not organizer and opportunity_type in TYPES_REQUIRING_ORGANIZER:
        logger.info(
            "      🚫 quality_filter REJET: pas d'organizer pour type '%s'",
            opportunity_type
        )
        return False

    logger.info("      ✅ quality_filter PASS: '%s'", title[:60])
    return True


# ============================================================
# NORMALISATION — AVEC LOGS
# ============================================================

def normalize_opportunity(opportunity: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Normalise les champs — AVEC LOGS."""

    if not isinstance(opportunity, dict):
        logger.info("      🚫 normalize REJET: pas un dict")
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

    # ============================================================
    # 1. is_actionable
    # ============================================================
    is_actionable = cleaned.get("is_actionable")

    if is_actionable is None:
        cleaned["is_actionable"] = True
    elif is_actionable is False:
        logger.info(
            "      🚫 normalize REJET: is_actionable=False | title='%s'",
            str(cleaned.get("title", "?"))[:50]
        )
        return None
    elif isinstance(is_actionable, str) and is_actionable.lower() in {"false", "no", "0"}:
        logger.info(
            "      🚫 normalize REJET: is_actionable='%s' | title='%s'",
            is_actionable, str(cleaned.get("title", "?"))[:50]
        )
        return None
    else:
        cleaned["is_actionable"] = True

    # ============================================================
    # 2. Conversion des types
    # ============================================================
    try:
        cleaned["confidence"] = float(cleaned.get("confidence", 0))
    except (TypeError, ValueError):
        cleaned["confidence"] = 0.0

    try:
        cleaned["score"] = int(float(cleaned.get("score", 0)))
    except (TypeError, ValueError):
        cleaned["score"] = 0

    # ============================================================
    # 3. Flag organizer ambigu
    # ============================================================
    _flag_ambiguous_organizer(cleaned)

    # ============================================================
    # 4. EXTRACTION EMPLOYEUR DEPUIS URL
    # ============================================================
    organizer = str(cleaned.get("organizer", "") or "").strip().lower()
    original_organizer = cleaned.get("organizer")

    platform_names_check = [
        "asako", "portaljob", "portal job", "job2mada",
        "codeko", "optioncarriere", "linkedin", "indeed",
        "glassdoor", "facebook",
    ]

    if any(p in organizer for p in platform_names_check):
        logger.info(
            "      🔍 Organizer = plateforme ('%s'), tentative d'extraction depuis URL...",
            original_organizer
        )

        extracted = _extract_employer_from_url(cleaned.get("url", ""))

        if extracted:
            cleaned["organizer"] = extracted
            logger.info(
                "      ✅ Organizer corrigé : '%s' → '%s'",
                original_organizer, extracted
            )
        else:
            logger.info(
                "      ⚠️ Impossible d'extraire l'employeur depuis l'URL, "
                "on garde '%s'",
                original_organizer
            )

    return cleaned


# ============================================================
# DÉDUPLICATION — AVEC LOGS
# ============================================================

def deduplicate(opportunities: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Déduplication par URL puis par titre normalisé — AVEC LOGS."""

    seen_urls = set()
    seen_titles = set()
    unique = []

    for opportunity in opportunities:
        url = str(opportunity.get("url", "")).strip().lower()
        title = re.sub(
            r"\s+", " ", str(opportunity.get("title", "")).strip().lower()
        )

        if url and url in seen_urls:
            logger.info(
                "      🔁 Doublon URL supprimé: %s",
                url[:80]
            )
            continue
        if title and title in seen_titles:
            logger.info(
                "      🔁 Doublon titre supprimé: '%s'",
                title[:60]
            )
            continue

        if url:
            seen_urls.add(url)
        if title:
            seen_titles.add(title)

        unique.append(opportunity)

    return unique


# ============================================================
# VALIDATION SCHÉMA (PYDANTIC) — AVEC LOGS
# ============================================================

def validate_against_schema(opportunity: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Valide la forme finale via le schéma Pydantic.
    Si validation échoue → bypass gracieux (retourne l'opportunité).
    """
    try:
        validated = OpportunityResult(**opportunity)
        return validated.model_dump()
    except ValidationError as exc:
        logger.warning(
            "      ⚠️ Validation Pydantic échouée pour '%s' : %s "
            "(BYPASS gracieux — retourné quand même)",
            str(opportunity.get("title", "?"))[:50],
            exc.errors()[:2],
        )
        return opportunity
    except Exception as exc:
        logger.error(
            "      ❌ Erreur inattendue validate_against_schema pour '%s' : %s "
            "(BYPASS gracieux — retourné quand même)",
            str(opportunity.get("title", "?"))[:50],
            exc,
        )
        return opportunity


# ============================================================
# FALLBACK RESPONSE
# ============================================================

def fallback_response(results: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Réponse de repli stricte."""
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