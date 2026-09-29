from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.models.facture import StatutFacture


class FactureCreate(BaseModel):
    client: str = Field(..., min_length=1)
    montant: float = Field(...,gt=0)
    tva_taux: float = Field(default=20.0, ge=0)
    date_echeance: date | None = None


class PaiementCreate(BaseModel):
    montant: float = Field(..., gt=0)
    date: date
    mode: str | None = None


class PaiementResponse(BaseModel):
    id: UUID
    montant: float
    date: date
    mode: str | None = None

    model_config = {"from_attributes": True}


class FactureResponse(BaseModel):
    id: UUID
    numero: str
    client: str
    montant: float
    tva_taux: float
    montant_ttc: float
    statut: StatutFacture
    date_emission: datetime
    date_echeance: date | None = None
    paiements: list[PaiementResponse] = []

    model_config = {"from_attributes": True}


class RelanceResponse(BaseModel):
    texte: str