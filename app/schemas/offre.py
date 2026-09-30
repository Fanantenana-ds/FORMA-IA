# app/schemas/offre.py
from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field

from app.models.offre import StatutOffre


class OffreCreate(BaseModel):
    titre: str = Field(..., min_length=1, max_length=255)
    client: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = None
    opportunite_id: Optional[UUID] = None
    tdr_document_id: Optional[UUID] = None
    trame_technique: Optional[str] = None
    trame_financiere: Optional[str] = None
    montant_ht: Optional[float] = Field(default=None, gt=0)
    tva_taux: float = Field(default=20.0, ge=0)
    statut: StatutOffre = StatutOffre.BROUILLON


class OffreUpdate(BaseModel):
    titre: Optional[str] = Field(default=None, min_length=1, max_length=255)
    client: Optional[str] = Field(default=None, min_length=1, max_length=100)
    description: Optional[str] = None
    trame_technique: Optional[str] = None
    trame_financiere: Optional[str] = None
    montant_ht: Optional[float] = Field(default=None, gt=0)
    tva_taux: Optional[float] = Field(default=None, ge=0)
    statut: Optional[StatutOffre] = None


class OffreReplace(BaseModel):
    """PUT — remplacement complet (tous les champs obligatoires sauf les optionnels métier)."""
    titre: str = Field(..., min_length=1, max_length=255)
    client: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = None
    opportunite_id: Optional[UUID] = None
    tdr_document_id: Optional[UUID] = None
    trame_technique: Optional[str] = None
    trame_financiere: Optional[str] = None
    montant_ht: Optional[float] = Field(default=None, gt=0)
    tva_taux: float = Field(default=20.0, ge=0)
    statut: StatutOffre = StatutOffre.BROUILLON


class OffreResponse(BaseModel):
    id: UUID
    titre: str
    client: str
    description: Optional[str] = None
    opportunite_id: Optional[UUID] = None
    tdr_document_id: Optional[UUID] = None
    trame_technique: Optional[str] = None
    trame_financiere: Optional[str] = None
    montant_ht: Optional[float] = None
    tva_taux: float
    montant_ttc: float
    statut: StatutOffre
    date_creation: datetime
    date_modification: Optional[datetime] = None

    model_config = {"from_attributes": True}
