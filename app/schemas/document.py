from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.models.document import FormatExport, StatutValidation, TypeDocument


class TDRRequest(BaseModel):
    opportunite_id: UUID | None = None
    client: str = Field(..., min_length=1)
    objectifs: str = Field(..., min_length=1)
    budget: float | None = Field(default=None, ge=0)
    echeance: datetime | None = None
    # Champs optionnels : TDR déjà rédigé par le module IA (M2)
    contenu: str | None = Field(default=None, max_length=500_000)
    format_export: FormatExport | None = None

class DocumentResponse(BaseModel):
    id: UUID
    type: TypeDocument
    contenu: str
    client: str | None = None
    objectifs: str | None = None
    format_export: FormatExport | None = None
    session_id: UUID | None = None
    participant_id: UUID | None = None
    numero_unique: str | None = None
    statut_validation: StatutValidation
    valide_par: UUID | None = None
    date_generation: datetime
    date_validation: datetime | None = None

    model_config = {
        "from_attributes": True,
    }

class ValidationRequest(BaseModel):
    approuve: bool

class OffreRequest(BaseModel):
    opportunite_id: UUID
    montant: float | None = Field(default=None, ge=0)
    # Optionnel : offre technique + financière rédigée par le module IA (M3).
    # Absent → le Backend génère son texte par défaut (comportement historique).
    contenu: str | None = Field(default=None, max_length=500_000)