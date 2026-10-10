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
    prenom: str | None = Field(default=None, max_length=100)
    email: str | None = Field(default=None, max_length=200)
    telephone: str | None = Field(default=None, max_length=30)
    adresse: str | None = Field(default=None, max_length=300)
    specialite: str | None = Field(default=None, max_length=200)
    tarif_journalier: float | None = Field(default=None, gt=0)
    notes_internes: str | None = None


class FormateurUpdate(BaseModel):
    nom: str | None = Field(default=None, max_length=100)
    prenom: str | None = Field(default=None, max_length=100)
    email: str | None = Field(default=None, max_length=200)
    telephone: str | None = Field(default=None, max_length=30)
    adresse: str | None = Field(default=None, max_length=300)
    specialite: str | None = Field(default=None, max_length=200)
    tarif_journalier: float | None = Field(default=None, gt=0)
    statut: str | None = None
    score_moyen: float | None = None
    nb_sessions: str | None = None
    recommandation: str | None = None
    notes_internes: str | None = None


class FormateurResponse(BaseModel):
    id: UUID
    nom: str
    prenom: str | None = None
    email: str | None = None
    telephone: str | None = None
    adresse: str | None = None
    specialite: str | None = None
    tarif_journalier: float | None = None
    statut: str
    score_moyen: float | None = None
    nb_sessions: str | None = None
    recommandation: str | None = None
    notes_internes: str | None = None
    date_creation: datetime
    model_config = {"from_attributes": True}


# ============================================================
# CANDIDAT
# ============================================================

class CandidatCreate(BaseModel):
    nom: str = Field(..., min_length=2, max_length=200)
    poste_vise: str = Field(..., min_length=2, max_length=200)
    cv_texte: str | None = None
    score_preselection: float | None = None
    decision_preselection: str | None = None
    review_id_preselection: str | None = Field(default=None, max_length=100)
    formateur_id: UUID | None = None


class CandidatUpdate(BaseModel):
    score_preselection: float | None = None
    decision_preselection: str | None = None
    review_id_preselection: str | None = Field(default=None, max_length=100)
    formateur_id: UUID | None = None


class CandidatResponse(BaseModel):
    id: UUID
    nom: str
    poste_vise: str
    score_preselection: float | None = None
    decision_preselection: str | None = None
    review_id_preselection: str | None = None
    formateur_id: UUID | None = None
    date_creation: datetime
    model_config = {"from_attributes": True}


# ============================================================
# ENTRETIEN
# ============================================================

class EntretienCreate(BaseModel):
    date_entretien: datetime | None = None
    interviewers: str | None = Field(default=None, max_length=500)
    notes_brutes: str | None = None
    compte_rendu: str | None = None
    decision: str | None = None
    review_id_entretien: str | None = Field(default=None, max_length=100)
    email_brouillon: str | None = None
    review_id_email: str | None = Field(default=None, max_length=100)


class EntretienUpdate(EntretienCreate):
    pass


class EntretienResponse(BaseModel):
    id: UUID
    candidat_id: UUID
    date_entretien: datetime | None = None
    interviewers: str | None = None
    notes_brutes: str | None = None
    compte_rendu: str | None = None
    decision: str | None = None
    review_id_entretien: str | None = None
    email_brouillon: str | None = None
    review_id_email: str | None = None
    date_creation: datetime
    model_config = {"from_attributes": True}
