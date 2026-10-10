# app/schemas/projet.py
from datetime import date, datetime, time
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, Field

from app.models.projet import StatutProjet

# ── Salle ───────────────────────────────────────────────────

class SalleCreate(BaseModel):
    nom: str = Field(..., min_length=1, max_length=100)
    adresse: str | None = None
    capacite: int | None = Field(default=None, gt=0)
    tarif_journalier: float | None = Field(default=None, gt=0)
    equipements: str | None = None
    disponible: bool = True


class SalleUpdate(BaseModel):
    nom: str | None = Field(default=None, min_length=1, max_length=100)
    adresse: str | None = None
    capacite: int | None = Field(default=None, gt=0)
    tarif_journalier: float | None = Field(default=None, gt=0)
    equipements: str | None = None
    disponible: bool | None = None


class SalleResponse(BaseModel):
    id: UUID
    nom: str
    adresse: str | None = None
    capacite: int | None = None
    tarif_journalier: float | None = None
    equipements: str | None = None
    disponible: bool
    date_creation: datetime

    model_config = {"from_attributes": True}


# ── Projet ──────────────────────────────────────────────────

class ProjetCreate(BaseModel):
    titre: str = Field(..., min_length=1, max_length=100)
    client: str | None = Field(default=None, max_length=100)
    date_debut: date | None = None
    date_fin: date | None = None
    statut: StatutProjet = StatutProjet.BROUILLON
    notes: str | None = None
    opportunite_id: UUID | None = None
    offre_id: UUID | None = None


class SalleReplace(BaseModel):
    """PUT — remplacement complet d'une salle."""
    nom: str = Field(..., min_length=1, max_length=100)
    adresse: str | None = None
    capacite: int | None = Field(default=None, gt=0)
    tarif_journalier: float | None = Field(default=None, gt=0)
    equipements: str | None = None
    disponible: bool = True


class ProjetReplace(BaseModel):
    """PUT — remplacement complet d'un projet."""
    titre: str = Field(..., min_length=1, max_length=100)
    client: str | None = Field(default=None, max_length=100)
    date_debut: date | None = None
    date_fin: date | None = None
    statut: StatutProjet = StatutProjet.BROUILLON
    notes: str | None = None
    opportunite_id: UUID | None = None
    offre_id: UUID | None = None


class ProjetUpdate(BaseModel):
    titre: str | None = Field(default=None, min_length=1, max_length=100)
    client: str | None = Field(default=None, max_length=100)
    date_debut: date | None = None
    date_fin: date | None = None
    statut: StatutProjet | None = None
    notes: str | None = None


class EdtSessionResponse(BaseModel):
    id: UUID
    projet_id: UUID
    date: date
    heure_debut: time | None = None
    heure_fin: time | None = None
    module: str | None = None
    formateur_id: UUID | None = None
    salle_id: UUID | None = None

    model_config = {"from_attributes": True}


class BudgetResponse(BaseModel):
    id: UUID
    projet_id: UUID
    cout_formateur: float
    cout_salle: float
    cout_supports: float
    cout_total: float
    valide: bool
    valide_par: UUID | None = None
    date_creation: datetime

    model_config = {"from_attributes": True}


class ProjetResponse(BaseModel):
    id: UUID
    titre: str
    client: str | None = None
    date_debut: date | None = None
    date_fin: date | None = None
    statut: StatutProjet
    notes: str | None = None
    opportunite_id: UUID | None = None
    offre_id: UUID | None = None
    date_creation: datetime

    model_config = {"from_attributes": True}


# ── EDT ─────────────────────────────────────────────────────

class EdtSessionCreate(BaseModel):
    date: date
    heure_debut: time | None = None
    heure_fin: time | None = None
    module: str | None = Field(default=None, max_length=200)
    formateur_id: UUID | None = None
    salle_id: UUID | None = None


# ── Budget ──────────────────────────────────────────────────

class BudgetCreate(BaseModel):
    cout_formateur: float = Field(default=0.0, ge=0)
    cout_salle: float = Field(default=0.0, ge=0)
    cout_supports: float = Field(default=0.0, ge=0)
    valide: bool = False
