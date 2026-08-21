from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field
from app.models.opportunite import (SourceOppotunite, Domaine, StatutOppoetunite)

class OpportuniteCreate(BaseModel):
    source: SourceOppotunite
    contenu: str = Field(..., min_length=1)
    objet: Optional[str] = None
    budget: Optional[float] = Field(default=None, ge=0)
    echeance: Optional[datetime] = None
    domaine: Optional[Domaine] = None

class OpportuniteResponse(BaseModel):
    id: UUID
    source: SourceOppotunite
    contenu: str

    objet: Optional[str] = None
    budget: Optional[float] = None
    echeance: Optional[datetime] = None
    domaine: Optional[Domaine] = None

    score_pertinente: float
    statut: StatutOppoetunite
    date_creation: datetime

    model_config = {
        "from_attributes": True
    }

class OpportuniteList(BaseModel):
    opportunites: list[OpportuniteResponse]
    total: int

class OpportuniteUpdate(BaseModel):
    source: str
    contenu: str
    objet: str
    budget: float | None = None
    echeance: datetime | None = None
    domaine: str