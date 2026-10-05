from datetime import datetime

from pydantic import BaseModel

from app.models.opportunite import Domaine


class AnalyseResult(BaseModel):
    objet: str | None = None
    budget: float | None = None
    echeance: datetime | None = None
    domaine: Domaine | None = None
    score_pertinence: float = 0.0