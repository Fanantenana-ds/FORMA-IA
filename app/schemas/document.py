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

class DocumentResponse(BaseModel):
    id: UUID
    type: TypeDocument
    contenu: str
    client: Optional[str] = None
    objectifs: Optional[str] = None
    format_export: Optional[FormatExport] = None
    statut_validation: StatutValidation
    valide_par: Optional[UUID] = None
    date_generation: datetime
    date_validation: Optional[datetime] = None

    model_config = {
        "from_attributes": True,
    }

class ValidationRequest(BaseModel):
    approuve: bool