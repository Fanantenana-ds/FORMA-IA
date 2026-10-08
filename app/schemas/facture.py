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


class FactureUpdate(BaseModel):
    """Mise à jour partielle d'une facture (tous les champs sont optionnels)."""
    client: Optional[str] = Field(default=None, min_length=1)
    date_echeance: Optional[date] = None
    statut: Optional[StatutFacture] = None


class RelanceResponse(BaseModel):
    texte: str


class RelanceIACreate(BaseModel):
    niveau: str = Field(..., pattern="^[123]$")
    objet: str = Field(..., min_length=1, max_length=200)
    texte: str = Field(..., min_length=10, max_length=10000)
    review_id: Optional[str] = Field(default=None, max_length=100)


class RelanceIAResponse(BaseModel):
    id: UUID
    facture_id: UUID
    niveau: str
    objet: str
    texte: str
    review_id: Optional[str] = None
    date_creation: datetime

    model_config = {"from_attributes": True}