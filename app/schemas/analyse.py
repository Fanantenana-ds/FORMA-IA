from datetime import datetime
from typing import Optional
from pydantic import BaseModel

from app.models.opportunite import Domaine

class AnalyseResult(BaseModel):
    objet: Optional[str] = None
    budget: Optional[float] = None
    echeance: Optional[datetime] = None
    domaine: Optional[Domaine] = None
    score_pertinente: float = 0.0