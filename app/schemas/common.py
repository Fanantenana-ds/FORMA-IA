from typing import Any, Dict, Optional

from pydantic import BaseModel


class RouteResponse(BaseModel):
    """Réponse standardisée pour toutes les routes IA (M3, M5, M6, M7, M8)."""
    success: bool
    message: str
    duration_seconds: Optional[float] = None
    review_id: Optional[str] = None
    review_status: Optional[str] = None
    requires_human_action: bool = False
    data: Optional[dict[str, Any]] = None
