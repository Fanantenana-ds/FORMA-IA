from typing import Any, Dict, Optional

from pydantic import BaseModel


class RouteResponse(BaseModel):
    """Réponse standardisée pour toutes les routes IA (M3, M5, M6, M7, M8)."""
    success: bool
    message: str
    duration_seconds: float | None = None
    review_id: str | None = None
    review_status: str | None = None
    requires_human_action: bool = False
    data: dict[str, Any] | None = None
