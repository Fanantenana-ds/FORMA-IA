# app/schemas/rh.py
# ============================================================
# SCHÉMAS BACKEND — M4 RH (Formateurs, Candidats, Entretiens)
# ============================================================

from datetime import datetime
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, Field


# ============================================================
# FORMATEUR
# ============================================================

class FormateurCreate(BaseModel):
    nom: str = Field(..., min_length=2, max_length=100)
    prenom: Optional[str] = Field(default=None, max_length=100)
    email: Optional[str] = Field(default=None, max_length=200)
    telephone: Optional[str] = Field(default=None, max_length=30)
    adresse: Optional[str] = Field(default=None, max_length=300)
    specialite: Optional[str] = Field(default=None, max_length=200)
    tarif_journalier: Optional[float] = Field(default=None, gt=0)
    notes_internes: Optional[str] = None


class FormateurUpdate(BaseModel):
    nom: Optional[str] = Field(default=None, max_length=100)
    prenom: Optional[str] = Field(default=None, max_length=100)
    email: Optional[str] = Field(default=None, max_length=200)
    telephone: Optional[str] = Field(default=None, max_length=30)
    adresse: Optional[str] = Field(default=None, max_length=300)
    specialite: Optional[str] = Field(default=None, max_length=200)
    tarif_journalier: Optional[float] = Field(default=None, gt=0)
    statut: Optional[str] = None
    score_moyen: Optional[float] = None
    nb_sessions: Optional[str] = None
    recommandation: Optional[str] = None
    notes_internes: Optional[str] = None


class FormateurResponse(BaseModel):
    id: UUID
    nom: str
    prenom: Optional[str] = None
    email: Optional[str] = None
    telephone: Optional[str] = None
    adresse: Optional[str] = None
    specialite: Optional[str] = None
    tarif_journalier: Optional[float] = None
    statut: str
    score_moyen: Optional[float] = None
    nb_sessions: Optional[str] = None
    recommandation: Optional[str] = None
    notes_internes: Optional[str] = None
    date_creation: datetime
    model_config = {"from_attributes": True}


# ============================================================
# CANDIDAT
# ============================================================

class CandidatCreate(BaseModel):
    nom: str = Field(..., min_length=2, max_length=200)
    poste_vise: str = Field(..., min_length=2, max_length=200)
    cv_texte: Optional[str] = None
    score_preselection: Optional[float] = None
    decision_preselection: Optional[str] = None
    review_id_preselection: Optional[str] = Field(default=None, max_length=100)
    formateur_id: Optional[UUID] = None


class CandidatUpdate(BaseModel):
    score_preselection: Optional[float] = None
    decision_preselection: Optional[str] = None
    review_id_preselection: Optional[str] = Field(default=None, max_length=100)
    formateur_id: Optional[UUID] = None


class CandidatResponse(BaseModel):
    id: UUID
    nom: str
    poste_vise: str
    score_preselection: Optional[float] = None
    decision_preselection: Optional[str] = None
    review_id_preselection: Optional[str] = None
    formateur_id: Optional[UUID] = None
    date_creation: datetime
    model_config = {"from_attributes": True}


# ============================================================
# ENTRETIEN
# ============================================================

class EntretienCreate(BaseModel):
    date_entretien: Optional[datetime] = None
    interviewers: Optional[str] = Field(default=None, max_length=500)
    notes_brutes: Optional[str] = None
    compte_rendu: Optional[str] = None
    decision: Optional[str] = None
    review_id_entretien: Optional[str] = Field(default=None, max_length=100)
    email_brouillon: Optional[str] = None
    review_id_email: Optional[str] = Field(default=None, max_length=100)


class EntretienUpdate(EntretienCreate):
    pass


class EntretienResponse(BaseModel):
    id: UUID
    candidat_id: UUID
    date_entretien: Optional[datetime] = None
    interviewers: Optional[str] = None
    decision: Optional[str] = None
    review_id_entretien: Optional[str] = None
    review_id_email: Optional[str] = None
    date_creation: datetime
    model_config = {"from_attributes": True}
