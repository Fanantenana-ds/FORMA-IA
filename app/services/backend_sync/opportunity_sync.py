# app/services/backend_sync/opportunity_sync.py
# ============================================================
# SERVICE BACKEND SYNC — Envoi des opportunités vers le Backend
# ============================================================
# Version : V2.0 — Budget en FLOAT + Mapping complet
# ============================================================
# Ce service envoie les opportunités détectées par M1 vers
# l'API Backend (FastAPI) qui les stocke en base PostgreSQL.
#
# Configuration (dans .env) :
#   BACKEND_SYNC_ENABLED, BACKEND_API_URL, BACKEND_SYNC_TOKEN,
#   BACKEND_SERVICE_EMAIL / BACKEND_SERVICE_PASSWORD, BACKEND_SYNC_TIMEOUT
#   → lues et gérées par base_sync.py (auth + re-login sur 401).
# ============================================================

import logging
import re
from typing import Any, Dict, List, Optional

from app.services.backend_sync import base_sync

logger = logging.getLogger(__name__)


# ============================================================
# MAPPING DOMAINE (M1 → Backend Enum)
# ============================================================

_DOMAIN_MAPPING = {
    "ia": "IA",
    "ai": "IA",
    "intelligence artificielle": "IA",
    "data": "DATA",
    "data science": "DATA",
    "devops": "DEVOPS",
    "dev": "DEVELOPPEMENT",
    "developpement": "DEVELOPPEMENT",
    "développement": "DEVELOPPEMENT",
    "bureautique": "BUREAUTIQUE",
    "autre": "AUTRE",
    "other": "AUTRE",
}


def _map_domain(domain: str) -> str:
    """Mappe le domaine M1 vers l'enum du Backend."""
    if not domain:
        return "AUTRE"
    return _DOMAIN_MAPPING.get(str(domain).lower().strip(), "AUTRE")


# ============================================================
# PARSING BUDGET (String → Float)
# ============================================================

def _parse_budget(budget_str: Any) -> float:
    """
    Convertit un budget string en float (ou 0.0 si non précisé).

    Supporte :
      - "5M Ar" → 5000000.0
      - "15 000 000 Ar" → 15000000.0
      - "5000000.50" → 5000000.5
      - "1,5M Ar" → 1500000.0
      - "1.234,56 Ar" (FR) → 1234.56
      - "1,234.56 Ar" (EN) → 1234.56
      - "Non précisé" → 0.0
    """
    if not budget_str:
        return 0.0

    text = str(budget_str).strip()
    if text.lower() in {
        "non précisé", "non precise", "non précisée",
        "n/a", "na", "null", "unknown", "non disponible",
    }:
        return 0.0

    # ✅ Détection multiplicateur (M = millions, K = milliers)
    # M / K collé ou séparé d'un espace du chiffre : "5M", "5 M", "5M Ar".
    # Pas de lettre ou chiffre derrière : ni "MGA", ni "150 m2".
    # (L'ancien \bM\b ne reconnaissait pas "5M" : pas de frontière entre 5 et M.)
    multiplier = 1.0
    if re.search(r"(?<=\d)\s?M(?![A-Za-z0-9])|millions?", text, re.IGNORECASE):
        multiplier = 1_000_000.0
    elif re.search(r"(?<=\d)\s?K(?![A-Za-z0-9])|milliers?", text, re.IGNORECASE):
        multiplier = 1_000.0

    # Extraire le nombre
    match = re.search(r"(\d+(?:[\s,.]\d+)*)", text)
    if not match:
        return 0.0

    number_str = match.group(1).replace(" ", "")

    # ✅ Nettoyage format (français vs anglais)
    if "," in number_str and "." in number_str:
        if number_str.rfind(",") > number_str.rfind("."):
            # Format français : 1.234,56
            number_str = number_str.replace(".", "").replace(",", ".")
        else:
            # Format anglais : 1,234.56
            number_str = number_str.replace(",", "")
    elif "," in number_str:
        # Décimal (5,50) ou millier (1,000)?
        if len(number_str.split(",")[-1]) <= 2:
            number_str = number_str.replace(",", ".")
        else:
            number_str = number_str.replace(",", "")

    try:
        value = float(number_str) * multiplier
        return round(value, 2)
    except (ValueError, TypeError):
        return 0.0


# ============================================================
# PARSING DEADLINE (String → ISO Date)
# ============================================================

def _parse_deadline(deadline_str: Any) -> Optional[str]:
    """
    Convertit une deadline en format ISO (YYYY-MM-DD).

    Supporte :
      - "2026-09-15" → "2026-09-15"
      - "15/09/2026" → "2026-09-15"
      - "2026-09-15T00:00:00" → "2026-09-15"
      - None / "Non précisée" → None
    """
    if not deadline_str:
        return None

    text = str(deadline_str).strip()
    if text.lower() in {
        "non précisé", "non précisée", "non precise",
        "n/a", "na", "null", "unknown",
    }:
        return None

    # Format ISO déjà
    if re.match(r"^\d{4}-\d{2}-\d{2}", text):
        return text[:10]

    # Format FR : 15/09/2026
    match = re.match(r"^(\d{1,2})/(\d{1,2})/(\d{4})$", text)
    if match:
        day, month, year = match.groups()
        return f"{year}-{month.zfill(2)}-{day.zfill(2)}"

    # Format FR avec tiret : 15-09-2026
    match = re.match(r"^(\d{1,2})-(\d{1,2})-(\d{4})$", text)
    if match:
        day, month, year = match.groups()
        return f"{year}-{month.zfill(2)}-{day.zfill(2)}"

    return None


# ============================================================
# CONSTRUCTION DU PAYLOAD BACKEND
# ============================================================

def _build_backend_payload(opportunity: Dict[str, Any]) -> Dict[str, Any]:
    """
    Construit le payload pour l'API Backend (POST /opportunites).

    Le Backend accepte (schéma OpportuniteCreate) :
      - source: enum SourceOpportunite (TEXTE, PDF, URL)
      - contenu: str (description)
      - objet: str (titre)
      - budget: float
      - echeance: date ISO (optionnel)
      - domaine: enum (IA, DATA, DEVOPS, DEVELOPPEMENT, BUREAUTIQUE, AUTRE)
    """
    # ✅ Concatène les infos enrichissantes dans "contenu"
    summary = str(opportunity.get("summary", "") or "").strip()
    organizer = str(opportunity.get("organizer", "") or "").strip()
    url = str(opportunity.get("url", "") or "").strip()
    score = opportunity.get("score", 0)
    confidence = opportunity.get("confidence", 0)
    status = opportunity.get("status", "to_review")
    opportunity_type = str(
        opportunity.get("opportunity_type", "") or ""
    ).strip()

    contenu_parts = [summary]
    if organizer:
        contenu_parts.append(f"Organisme : {organizer}")
    if opportunity_type:
        contenu_parts.append(f"Type : {opportunity_type}")
    if url:
        contenu_parts.append(f"Lien : {url}")

    contenu = " | ".join(filter(None, contenu_parts))

    payload = {
        # Enum Backend SourceOpportunite = TEXTE | PDF | URL
        # ("VEILLE_IA" n'existe pas : le Backend répondait HTTP 422)
        "source": "URL" if url else "TEXTE",
        "contenu": contenu[:5000],  # Limite raisonnable
        "objet": str(opportunity.get("title", "Sans titre"))[:500],
        "budget": _parse_budget(opportunity.get("budget")),
        "echeance": _parse_deadline(opportunity.get("deadline")),
        "domaine": _map_domain(opportunity.get("domain", "")),
    }

    return payload


# ============================================================
# FONCTION PRINCIPALE — SYNC
# ============================================================

async def sync_opportunities_to_backend(
    opportunities: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """
    Envoie les opportunités vers le Backend (POST /opportunites).

    Retourne :
      {
        "enabled": bool,     # Backend sync activé ?
        "sent": int,         # Nombre d'opportunités envoyées
        "failed": int,       # Nombre d'échecs
      }

    Comportement :
      - Si BACKEND_SYNC_ENABLED=false → skip (pas d'erreur)
      - Si aucune opportunité → skip
      - Sinon → POST pour chaque opportunité
    """
    result = {
        "enabled": base_sync.is_sync_enabled(),
        "sent": 0,
        "failed": 0,
    }

    # ------------------------------------------------------------
    # 1. Vérifications préliminaires
    # ------------------------------------------------------------
    if not result["enabled"]:
        logger.info(
            "ℹ️ Backend sync DÉSACTIVÉ "
            "(BACKEND_SYNC_ENABLED=false dans .env)"
        )
        return result

    if not opportunities:
        logger.info("ℹ️ Aucune opportunité à synchroniser")
        return result

    logger.info(
        "📤 Backend sync : envoi de %d opportunité(s)", len(opportunities)
    )

    # ------------------------------------------------------------
    # 2. Envoi de chaque opportunité
    #    (authentification + re-login sur 401 : gérés par base_sync)
    # ------------------------------------------------------------
    for idx, opp in enumerate(opportunities, start=1):
        title_preview = str(opp.get("title", "?"))[:60]

        try:
            payload = _build_backend_payload(opp)

            logger.debug(
                "   [%d/%d] Payload : %s",
                idx, len(opportunities), payload
            )

            response = await base_sync.backend_request(
                "POST", "/opportunites", json=payload
            )

            if response["ok"]:
                result["sent"] += 1
                logger.info(
                    "   ✅ [%d/%d] Envoyé : '%s'",
                    idx, len(opportunities), title_preview
                )
            else:
                result["failed"] += 1
                logger.warning(
                    "   ❌ [%d/%d] Échec : '%s' | %s",
                    idx, len(opportunities),
                    title_preview, response["error"]
                )

        except Exception as exc:
            result["failed"] += 1
            logger.exception(
                "   ❌ [%d/%d] Erreur inattendue : '%s' | %s",
                idx, len(opportunities),
                title_preview, exc
            )

    # ------------------------------------------------------------
    # 3. Résumé
    # ------------------------------------------------------------
    logger.info(
        "📊 Backend sync TERMINÉ : %d envoyés, %d échoués (sur %d)",
        result["sent"], result["failed"], len(opportunities)
    )

    return result


# ============================================================
# SYNC SANS DOUBLONS — détection automatique répétée
# ============================================================

def _cle_titre(titre: Any) -> str:
    """Titre normalisé, tronqué comme la colonne Backend (objet = 255)."""
    return re.sub(r"\s+", " ", str(titre or "").strip().lower())[:255]


def _liste_backend(data: Any) -> List[Dict[str, Any]]:
    if isinstance(data, list):
        return [o for o in data if isinstance(o, dict)]
    if isinstance(data, dict):
        liste = data.get("opportunites") or data.get("items") or []
        return [o for o in liste if isinstance(o, dict)]
    return []


async def sync_new_opportunities_to_backend(
    opportunities: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """
    Comme sync_opportunities_to_backend, mais n'envoie QUE les opportunités
    absentes du Backend (même URL déjà présente dans un contenu, ou même
    titre). Indispensable en mode automatique : chaque passage retrouve les
    mêmes annonces et les recréerait à chaque fois.

    Si la liste du Backend est illisible, RIEN n'est envoyé (mieux vaut
    manquer un passage que créer des doublons) : la clé "error" l'explique.

    Retourne {enabled, sent, failed, already_present[, error]}.
    """
    result: Dict[str, Any] = {
        "enabled": base_sync.is_sync_enabled(),
        "sent": 0,
        "failed": 0,
        "already_present": 0,
    }
    if not result["enabled"] or not opportunities:
        return result

    response = await base_sync.backend_request("GET", "/opportunites")
    if not response["ok"]:
        result["error"] = (
            "Doublons non vérifiables, envoi annulé : "
            f"{response['error']}"
        )
        logger.warning("⚠️ %s", result["error"])
        return result

    existantes = _liste_backend(response["data"])
    titres_connus = {_cle_titre(o.get("objet")) for o in existantes}
    titres_connus.discard("")
    contenus = [str(o.get("contenu") or "").lower() for o in existantes]

    nouvelles: List[Dict[str, Any]] = []
    for opp in opportunities:
        url = str(opp.get("url") or "").strip().lower()
        deja = _cle_titre(opp.get("title")) in titres_connus or (
            bool(url) and any(url in contenu for contenu in contenus)
        )
        if deja:
            result["already_present"] += 1
        else:
            nouvelles.append(opp)

    if nouvelles:
        envoi = await sync_opportunities_to_backend(nouvelles)
        result["sent"] = envoi["sent"]
        result["failed"] = envoi["failed"]

    logger.info(
        "📊 Sync sans doublons : %d envoyées, %d déjà présentes, %d échecs",
        result["sent"], result["already_present"], result["failed"],
    )
    return result


# ============================================================
# FONCTION UTILITAIRE — TEST MANUEL
# ============================================================

async def test_sync_single_opportunity(opportunity: Dict[str, Any]) -> bool:
    """
    Teste l'envoi d'UNE SEULE opportunité (pour debug).
    Retourne True si succès, False sinon.
    """
    result = await sync_opportunities_to_backend([opportunity])
    return result.get("sent", 0) == 1 and result.get("failed", 0) == 0