from datetime import datetime
from typing import Optional
from uuid import UUID
from pydantic import BaseModel, Field
from app.models.document import TypeDocument, FormatExport, StatutValidation

class TDRRequest(BaseModel):
    opportunite_id: Optional[UUID] = None
    client: str = Field(..., min_length=1)
    objectifs: str = Field(..., min_length=1)
    budget: Optional[float] = Field(default=None, ge=0)
    echeance: Optional[datetime] = None
    # Champs optionnels : TDR déjà rédigé par le module IA (M2)
    contenu: Optional[str] = Field(default=None, max_length=500_000)
    format_export: Optional[FormatExport] = None

class DocumentResponse(BaseModel):
    id: UUID
    type: TypeDocument
    contenu: str
    client: Optional[str] = None
    objectifs: Optional[str] = None
    format_export: Optional[FormatExport] = None
    session_id: Optional[UUID] = None
    participant_id: Optional[UUID] = None
    numero_unique: Optional[str] = None
    statut_validation: StatutValidation
    valide_par: Optional[UUID] = None
    date_generation: datetime
    date_validation: Optional[datetime] = None

    model_config = {
        "from_attributes": True,
    }

class ValidationRequest(BaseModel):
    approuve: bool

class OffreRequest(BaseModel):
    opportunite_id: UUID
    montant: Optional[float] = Field(default=None, ge=0)
    # Optionnel : offre technique + financière rédigée par le module IA (M3).
    # Absent → le Backend génère son texte par défaut (comportement historique).
    contenu: Optional[str] = Field(default=None, max_length=500_000)