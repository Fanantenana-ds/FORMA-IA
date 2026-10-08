# app/schemas/projet.py
from datetime import date, datetime, time
from typing import Optional, List
from uuid import UUID

from pydantic import BaseModel, Field

from app.models.projet import StatutProjet


# ── Salle ───────────────────────────────────────────────────

class SalleCreate(BaseModel):
    nom: str = Field(..., min_length=1, max_length=100)
    adresse: Optional[str] = None
    capacite: Optional[int] = Field(default=None, gt=0)
    tarif_journalier: Optional[float] = Field(default=None, gt=0)
    equipements: Optional[str] = None
    disponible: bool = True


class SalleUpdate(BaseModel):
    nom: Optional[str] = Field(default=None, min_length=1, max_length=100)
    adresse: Optional[str] = None
    capacite: Optional[int] = Field(default=None, gt=0)
    tarif_journalier: Optional[float] = Field(default=None, gt=0)
    equipements: Optional[str] = None
    disponible: Optional[bool] = None


class SalleResponse(BaseModel):
    id: UUID
    nom: str
    adresse: Optional[str] = None
    capacite: Optional[int] = None
    tarif_journalier: Optional[float] = None
    equipements: Optional[str] = None
    disponible: bool
    date_creation: datetime

    model_config = {"from_attributes": True}


# ── Projet ──────────────────────────────────────────────────

class ProjetCreate(BaseModel):
    titre: str = Field(..., min_length=1, max_length=100)
    client: Optional[str] = Field(default=None, max_length=100)
    date_debut: Optional[date] = None
    date_fin: Optional[date] = None
    statut: StatutProjet = StatutProjet.BROUILLON
    notes: Optional[str] = None
    opportunite_id: Optional[UUID] = None
    offre_id: Optional[UUID] = None


class SalleReplace(BaseModel):
    """PUT — remplacement complet d'une salle."""
    nom: str = Field(..., min_length=1, max_length=100)
    adresse: Optional[str] = None
    capacite: Optional[int] = Field(default=None, gt=0)
    tarif_journalier: Optional[float] = Field(default=None, gt=0)
    equipements: Optional[str] = None
    disponible: bool = True


class ProjetReplace(BaseModel):
    """PUT — remplacement complet d'un projet."""
    titre: str = Field(..., min_length=1, max_length=100)
    client: Optional[str] = Field(default=None, max_length=100)
    date_debut: Optional[date] = None
    date_fin: Optional[date] = None
    statut: StatutProjet = StatutProjet.BROUILLON
    notes: Optional[str] = None
    opportunite_id: Optional[UUID] = None
    offre_id: Optional[UUID] = None


class ProjetUpdate(BaseModel):
    titre: Optional[str] = Field(default=None, min_length=1, max_length=100)
    client: Optional[str] = Field(default=None, max_length=100)
    date_debut: Optional[date] = None
    date_fin: Optional[date] = None
    statut: Optional[StatutProjet] = None
    notes: Optional[str] = None


class EdtSessionResponse(BaseModel):
    id: UUID
    projet_id: UUID
    date: date
    heure_debut: Optional[time] = None
    heure_fin: Optional[time] = None
    module: Optional[str] = None
    formateur_id: Optional[UUID] = None
    salle_id: Optional[UUID] = None

    model_config = {"from_attributes": True}


class BudgetResponse(BaseModel):
    id: UUID
    projet_id: UUID
    cout_formateur: float
    cout_salle: float
    cout_supports: float
    cout_total: float
    valide: bool
    valide_par: Optional[UUID] = None
    date_creation: datetime

    model_config = {"from_attributes": True}


class ProjetResponse(BaseModel):
    id: UUID
    titre: str
    client: Optional[str] = None
    date_debut: Optional[date] = None
    date_fin: Optional[date] = None
    statut: StatutProjet
    notes: Optional[str] = None
    opportunite_id: Optional[UUID] = None
    offre_id: Optional[UUID] = None
    date_creation: datetime

    model_config = {"from_attributes": True}


# ── EDT ─────────────────────────────────────────────────────

class EdtSessionCreate(BaseModel):
    date: date
    heure_debut: Optional[time] = None
    heure_fin: Optional[time] = None
    module: Optional[str] = Field(default=None, max_length=200)
    formateur_id: Optional[UUID] = None
    salle_id: Optional[UUID] = None


# ── Budget ──────────────────────────────────────────────────

class BudgetCreate(BaseModel):
    cout_formateur: float = Field(default=0.0, ge=0)
    cout_salle: float = Field(default=0.0, ge=0)
    cout_supports: float = Field(default=0.0, ge=0)
    valide: bool = False
