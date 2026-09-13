# app/services/backend_sync/tdr_sync.py
# ============================================================
# SYNC TDR → BACKEND (via API)
# ============================================================
# Envoie le TDR généré par M2 vers l'API Backend pour stockage
# dans la table `documents`.
# ============================================================

import json
import logging
import os
from typing import Any, Dict, Optional

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
BACKEND_SERVICE_EMAIL = os.getenv("BACKEND_SERVICE_EMAIL", "")
BACKEND_SERVICE_PASSWORD = os.getenv("BACKEND_SERVICE_PASSWORD", "")
BACKEND_SYNC_TIMEOUT = float(os.getenv("BACKEND_SYNC_TIMEOUT", "30"))


# ============================================================
# AUTO-LOGIN (même logique que M1)
# ============================================================

async def _get_backend_token() -> Optional[str]:
    """Récupère un JWT token (env ou auto-login)."""
    if BACKEND_SYNC_TOKEN:
        return BACKEND_SYNC_TOKEN

    if not BACKEND_SERVICE_EMAIL or not BACKEND_SERVICE_PASSWORD:
        logger.warning(
            "⚠️ Pas de token ni credentials service — sync impossible"
        )
        return None

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                f"{BACKEND_API_URL}/auth/login",
                json={
                    "email": BACKEND_SERVICE_EMAIL,
                    "password": BACKEND_SERVICE_PASSWORD,
                },
            )

            if response.status_code == 200:
                data = response.json()
                token = data.get("access_token")
                logger.info("✅ Token Backend obtenu via auto-login")
                return token
            else:
                logger.error(
                    "❌ Auto-login échoué : HTTP %d | %s",
                    response.status_code, response.text[:200]
                )
                return None
    except Exception as exc:
        logger.error("❌ Erreur auto-login : %s", exc)
        return None


# ============================================================
# BUILD PAYLOAD
# ============================================================

def _build_tdr_payload(
    tdr_content: Dict[str, Any],
    docx_filename: Optional[str],
    pdf_filename: Optional[str],
    opportunite_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Construit le payload pour POST /documents."""
    return {
        "type": "TDR",
        "contenu": json.dumps(tdr_content, ensure_ascii=False),
        "client": tdr_content.get("client", "Client"),
        "objectifs": tdr_content.get("objectif_general", ""),
        "format_export": "PDF" if pdf_filename else "WORD",
        "opportunite_id": opportunite_id,
        "chemin_fichier": pdf_filename or docx_filename or "",
    }


# ============================================================
# SYNC
# ============================================================

async def sync_tdr_to_backend(
    tdr_content: Dict[str, Any],
    docx_filename: Optional[str] = None,
    pdf_filename: Optional[str] = None,
    opportunite_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Envoie le TDR vers le Backend.
    
    Retourne :
      {
        "enabled": bool,
        "sent": bool,
        "document_id": str | None,
        "error": str | None
      }
    """
    result = {
        "enabled": BACKEND_SYNC_ENABLED,
        "sent": False,
        "document_id": None,
        "error": None,
    }

    # 1. Vérifications
    if not BACKEND_SYNC_ENABLED:
        logger.info("ℹ️ Backend sync DÉSACTIVÉ (BACKEND_SYNC_ENABLED=false)")
        return result

    if not tdr_content:
        result["error"] = "Aucun contenu TDR à synchroniser"
        return result

    # 2. Token
    token = await _get_backend_token()
    if not token:
        result["error"] = "Impossible d'obtenir un token Backend"
        logger.error("❌ Sync TDR annulée : %s", result["error"])
        return result

    # 3. Payload
    payload = _build_tdr_payload(
        tdr_content=tdr_content,
        docx_filename=docx_filename,
        pdf_filename=pdf_filename,
        opportunite_id=opportunite_id,
    )

    logger.info(
        "📤 Sync TDR vers Backend : client='%s', format=%s",
        payload["client"], payload["format_export"]
    )

    # 4. Envoi
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {token}",
    }

    try:
        async with httpx.AsyncClient(timeout=BACKEND_SYNC_TIMEOUT) as client:
            response = await client.post(
                f"{BACKEND_API_URL}/documents",
                json=payload,
                headers=headers,
            )

            if response.status_code in (200, 201):
                data = response.json()
                result["sent"] = True
                result["document_id"] = data.get("id")
                logger.info(
                    "   ✅ TDR synchronisé (document_id=%s)",
                    result["document_id"]
                )
            else:
                result["error"] = (
                    f"HTTP {response.status_code} : {response.text[:200]}"
                )
                logger.warning(
                    "   ❌ Échec sync TDR : %s", result["error"]
                )

    except httpx.TimeoutException:
        result["error"] = "Timeout Backend"
        logger.error("   ❌ Timeout sync TDR")
    except Exception as exc:
        result["error"] = str(exc)
        logger.exception("   ❌ Erreur sync TDR : %s", exc)

    return result