# app/services/backend_sync/opportunity_sync.py
# ============================================================
# SYNCHRONISATION OPTIONNELLE VERS LE BACKEND
# ============================================================
# M1 reste 100% autonome : ce module ne fait RIEN si le flag
# BACKEND_SYNC_ENABLED n'est pas à "true", et ne fait jamais
# planter M1 même en cas d'échec réseau (backend éteint,
# endpoint pas encore prêt, etc.).
#
# Aucun import SQLAlchemy ici — uniquement un appel HTTP vers
# l'API RESTful exposée par le Backend (POST /api/v1/opportunities),
# conformément au découpage des rôles.
# ============================================================

import logging
import os
from typing import Any, Dict, List

import httpx

logger = logging.getLogger(__name__)

BACKEND_SYNC_ENABLED = os.getenv(
    "BACKEND_SYNC_ENABLED", "false"
).lower() == "true"

BACKEND_API_URL = os.getenv(
    "BACKEND_API_URL", "http://localhost:8000/api/v1"
)

BACKEND_SYNC_TIMEOUT = float(
    os.getenv("BACKEND_SYNC_TIMEOUT", "5")
)


async def sync_opportunities_to_backend(
    opportunities: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    Tente d'envoyer les opportunités validées au Backend
    (POST /api/v1/opportunities), une par une.

    Ne lève JAMAIS d'exception : un échec ici ne doit jamais
    empêcher M1 de répondre à l'utilisateur.

    Retourne un résumé (jamais bloquant pour l'appelant).
    """
    if not BACKEND_SYNC_ENABLED:
        logger.debug(
            "ℹ️ BACKEND_SYNC désactivé — M1 fonctionne en autonome"
        )
        return {"enabled": False, "sent": 0, "failed": 0}

    if not opportunities:
        return {"enabled": True, "sent": 0, "failed": 0}

    sent = 0
    failed = 0

    try:
        async with httpx.AsyncClient(
            timeout=BACKEND_SYNC_TIMEOUT
        ) as client:

            for opportunity in opportunities:
                try:
                    response = await client.post(
                        f"{BACKEND_API_URL}/opportunities",
                        json=opportunity,
                    )

                    if response.status_code in (200, 201):
                        sent += 1
                    else:
                        failed += 1
                        logger.warning(
                            "⚠️ Backend a refusé l'opportunité "
                            "(HTTP %s) : %s",
                            response.status_code,
                            opportunity.get("title", "?"),
                        )

                except httpx.HTTPError as exc:
                    failed += 1
                    logger.warning(
                        "⚠️ Backend injoignable pour une opportunité "
                        "(non bloquant) : %s",
                        exc,
                    )

    except Exception as exc:
        logger.error(
            "❌ Synchronisation backend échouée (non bloquant "
            "pour M1) : %s",
            exc,
        )
        return {"enabled": True, "sent": sent, "failed": failed, "error": str(exc)}

    logger.info(
        "🔄 Sync backend : %d envoyées / %d échouées", sent, failed
    )

    return {"enabled": True, "sent": sent, "failed": failed}