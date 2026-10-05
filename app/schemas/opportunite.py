from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field, HttpUrl, model_validator

from app.models.opportunite import Domaine, SourceOpportunite, StatutOpportunite


class OpportuniteCreate(BaseModel):
    source: SourceOpportunite
    contenu: str = Field(..., min_length=1)
    objet: str | None = None
    budget: float | None = Field(default=None, ge=0)
    echeance: datetime | None = None
    domaine: Domaine | None = None

class OpportuniteResponse(BaseModel):
    id: UUID
    source: SourceOpportunite
    contenu: str

    objet: str | None = None
    budget: float | None = None
    echeance: datetime | None = None
    domaine: Domaine | None = None

    score_pertinence: float
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
    contenu: str | None = None
    url: HttpUrl | None = None

    @model_validator(mode="after")
    def valide_source(self):
        if not self.contenu and not self.url:
            raise ValueError(
                "Le contenu ou l'URL doit être renseigné."
            )
        
        return self

class OpportuniteAnalyseResult(BaseModel):
    objet: str | None = None
    budget: float | None = Field(default=None, ge=0)
    echeance: datetime | None = None
    domaine: Domaine | None = None
    score_pertinence: float = Field(
        ...,
        ge=0,
        le=1.0
    )