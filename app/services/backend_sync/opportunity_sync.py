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
#   BACKEND_SYNC_ENABLED=true|false
#   BACKEND_API_URL=http://localhost:8000/api/v1
#   BACKEND_SYNC_TOKEN=<token JWT si nécessaire>
# ============================================================

import logging
import os
import re
from typing import Any, Dict, List, Optional

import httpx

logger = logging.getLogger(__name__)


# ============================================================
# CONFIGURATION (depuis .env)
# ============================================================

BACKEND_SYNC_ENABLED = (
    os.getenv("BACKEND_SYNC_ENABLED", "false").lower() == "true"
)
BACKEND_API_URL = os.getenv(
    "BACKEND_API_URL", "http://localhost:8000/api/v1"
)
BACKEND_SYNC_TOKEN = os.getenv("BACKEND_SYNC_TOKEN", "")
BACKEND_SYNC_TIMEOUT = float(os.getenv("BACKEND_SYNC_TIMEOUT", "30"))


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
    multiplier = 1.0
    if re.search(r"\bM\b|millions?", text, re.IGNORECASE):
        multiplier = 1_000_000.0
    elif re.search(r"\bK\b|milliers?", text, re.IGNORECASE):
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
      - source: enum (TEXTE, PDF, VEILLE_IA, ...)
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
        "source": "VEILLE_IA",
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
        "enabled": BACKEND_SYNC_ENABLED,
        "sent": 0,
        "failed": 0,
    }

    # ------------------------------------------------------------
    # 1. Vérifications préliminaires
    # ------------------------------------------------------------
    if not BACKEND_SYNC_ENABLED:
        logger.info(
            "ℹ️ Backend sync DÉSACTIVÉ "
            "(BACKEND_SYNC_ENABLED=false dans .env)"
        )
        return result

    if not opportunities:
        logger.info("ℹ️ Aucune opportunité à synchroniser")
        return result

    logger.info(
        "📤 Backend sync : envoi de %d opportunité(s) vers %s",
        len(opportunities), BACKEND_API_URL
    )

    # ------------------------------------------------------------
    # 2. Préparation des headers
    # ------------------------------------------------------------
    headers = {"Content-Type": "application/json"}
    if BACKEND_SYNC_TOKEN:
        headers["Authorization"] = f"Bearer {BACKEND_SYNC_TOKEN}"

    # ------------------------------------------------------------
    # 3. Envoi de chaque opportunité
    # ------------------------------------------------------------
    async with httpx.AsyncClient(timeout=BACKEND_SYNC_TIMEOUT) as client:
        for idx, opp in enumerate(opportunities, start=1):
            title_preview = str(opp.get("title", "?"))[:60]

            try:
                payload = _build_backend_payload(opp)

                logger.debug(
                    "   [%d/%d] Payload : %s",
                    idx, len(opportunities), payload
                )

                response = await client.post(
                    f"{BACKEND_API_URL}/opportunites",
                    json=payload,
                    headers=headers,
                )

                if response.status_code in (200, 201):
                    result["sent"] += 1
                    logger.info(
                        "   ✅ [%d/%d] Envoyé : '%s'",
                        idx, len(opportunities), title_preview
                    )
                else:
                    result["failed"] += 1
                    logger.warning(
                        "   ❌ [%d/%d] Échec HTTP %d : '%s' | %s",
                        idx, len(opportunities),
                        response.status_code,
                        title_preview,
                        response.text[:200]
                    )

            except httpx.TimeoutException:
                result["failed"] += 1
                logger.error(
                    "   ❌ [%d/%d] Timeout : '%s'",
                    idx, len(opportunities), title_preview
                )
            except httpx.HTTPError as exc:
                result["failed"] += 1
                logger.error(
                    "   ❌ [%d/%d] Erreur HTTP : '%s' | %s",
                    idx, len(opportunities),
                    title_preview, exc
                )
            except Exception as exc:
                result["failed"] += 1
                logger.exception(
                    "   ❌ [%d/%d] Erreur inattendue : '%s' | %s",
                    idx, len(opportunities),
                    title_preview, exc
                )

    # ------------------------------------------------------------
    # 4. Résumé
    # ------------------------------------------------------------
    logger.info(
        "📊 Backend sync TERMINÉ : %d envoyés, %d échoués (sur %d)",
        result["sent"], result["failed"], len(opportunities)
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