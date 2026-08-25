from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field, HttpUrl, model_validator
from app.models.opportunite import (SourceOpportunite, Domaine, StatutOpportunite)

class OpportuniteCreate(BaseModel):
    source: SourceOpportunite
    contenu: str = Field(..., min_length=1)
    objet: Optional[str] = None
    budget: Optional[float] = Field(default=None, ge=0)
    echeance: Optional[datetime] = None
    domaine: Optional[Domaine] = None

class OpportuniteResponse(BaseModel):
    id: UUID
    source: SourceOpportunite
    contenu: str

    objet: Optional[str] = None
    budget: Optional[float] = None
    echeance: Optional[datetime] = None
    domaine: Optional[Domaine] = None

    score_pertinente: float
    statut: StatutOpportunite
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

class OpportuniteAnalyseRequest(BaseModel):
    contenu: Optional[str] = None
    url: Optional[HttpUrl] = None

    @model_validator(mode="after")
    def valide_source(self):
        if not self.contenu and not self.url:
            raise ValueError(
                "Le contenu ou l'URL doit être renseigné."
            )
        
        return self

class OpportuniteAnalyseResult(BaseModel):
    objet: Optional[str] = None
    budget: Optional[float] = Field(default=None, ge=0)
    echeance: Optional[datetime] = None
    domaine: Optional[Domaine] = None
    score_pertinente: float = Field(
        ...,
        ge=0,
        le=1.0
    )