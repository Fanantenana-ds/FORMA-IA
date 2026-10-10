# app/schemas/offre.py
from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field

from app.models.offre import StatutOffre


class OffreCreate(BaseModel):
    titre: str = Field(..., min_length=1, max_length=255)
    client: str = Field(..., min_length=1, max_length=100)
    description: str | None = None
    opportunite_id: UUID | None = None
    tdr_document_id: UUID | None = None
    trame_technique: str | None = None
    trame_financiere: str | None = None
    montant_ht: float | None = Field(default=None, gt=0)
    tva_taux: float = Field(default=20.0, ge=0)
    statut: StatutOffre = StatutOffre.BROUILLON


class OffreUpdate(BaseModel):
    titre: str | None = Field(default=None, min_length=1, max_length=255)
    client: str | None = Field(default=None, min_length=1, max_length=100)
    description: str | None = None
    trame_technique: str | None = None
    trame_financiere: str | None = None
    montant_ht: float | None = Field(default=None, gt=0)
    tva_taux: float | None = Field(default=None, ge=0)
    statut: StatutOffre | None = None


class OffreReplace(BaseModel):
    """PUT — remplacement complet (tous les champs obligatoires sauf les optionnels métier)."""
    titre: str = Field(..., min_length=1, max_length=255)
    client: str = Field(..., min_length=1, max_length=100)
    description: str | None = None
    opportunite_id: UUID | None = None
    tdr_document_id: UUID | None = None
    trame_technique: str | None = None
    trame_financiere: str | None = None
    montant_ht: float | None = Field(default=None, gt=0)
    tva_taux: float = Field(default=20.0, ge=0)
    statut: StatutOffre = StatutOffre.BROUILLON


class OffreResponse(BaseModel):
    id: UUID
    titre: str
    client: str
    description: str | None = None
    opportunite_id: UUID | None = None
    tdr_document_id: UUID | None = None
    trame_technique: str | None = None
    trame_financiere: str | None = None
    montant_ht: float | None = None
    tva_taux: float
    montant_ttc: float
    statut: StatutOffre
    date_creation: datetime
    date_modification: datetime | None = None

    model_config = {"from_attributes": True}
