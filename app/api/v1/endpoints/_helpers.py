import logging
import os
from typing import Any, Dict

from fastapi import HTTPException

from app.schemas.common import RouteResponse

_VERBOSE = os.getenv("VERBOSE_LOGS", "true").lower() == "true"


def _vlog(logger: logging.Logger, msg: str) -> None:
    if _VERBOSE:
        logger.info(msg)


def log_request(logger: logging.Logger, tag: str, method: str, path: str, **kwargs) -> None:
    _vlog(logger, "=" * 70)
    _vlog(logger, f"🌐 [{tag}] {method} {path}")
    for k, val in kwargs.items():
        _vlog(logger, f"   {k} : {val}")
    _vlog(logger, "=" * 70)


def handle_exception(
    e: Exception,
    context: str,
    tag: str,
    logger: logging.Logger,
    not_found_on_value_error: bool = False,
) -> None:
    """
    not_found_on_value_error=True : si ValueError contient 'introuvable', retourne 404
    (comportement M7 facturation).
    """
    if isinstance(e, NotImplementedError):
        logger.warning(f"⚠️  [{tag}] {context} : {e}")
        raise HTTPException(status_code=501, detail=str(e))
    if isinstance(e, ValueError):
        if not_found_on_value_error and "introuvable" in str(e).lower():
            raise HTTPException(status_code=404, detail=str(e))
        logger.error(f"❌ [{tag}] {context} — validation : {e}")
        raise HTTPException(status_code=422, detail=f"Données invalides : {e}")
    if isinstance(e, RuntimeError):
        logger.error(f"❌ [{tag}] {context} — service : {e}")
        raise HTTPException(status_code=503, detail=str(e))
    logger.exception(f"💥 [{tag}] {context} : {e}")
    raise HTTPException(
        status_code=500,
        detail=f"Erreur interne : {type(e).__name__} — {e}",
    )


def build_response(result: dict[str, Any], msg_ok: str, elapsed: float) -> RouteResponse:
    """Construit une réponse uniforme avec info HITL."""
    review_id = result.get("_review_id") if isinstance(result, dict) else None
    status_val = result.get("_review_status") if isinstance(result, dict) else None
    requires_action = status_val == "pending_review"
    message = msg_ok
    if requires_action:
        message += f" ⚠️ En attente validation (review={review_id})."
    return RouteResponse(
        success=True,
        message=message,
        duration_seconds=elapsed,
        review_id=review_id,
        review_status=status_val,
        requires_human_action=requires_action,
        data=result,
    )
