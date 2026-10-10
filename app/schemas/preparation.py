from datetime import date, time
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, Field

from app.models.preparation import StatutProjet


class ProjetCreate(BaseModel):
    marche_id: UUID | None = None
    tdr_id: UUID | None = None
    client_id: UUID | None = None
    titre: str = Field(..., min_length=1)
    date_debut: date | None = None
    date_fin: date | None = None
    budget: float | None = Field(default=None, ge=0)


class ProjetUpdate(BaseModel):
    marche_id: UUID | None = None
    tdr_id: UUID | None = None
    client_id: UUID | None = None
    titre: str | None = Field(default=None, min_length=1)
    date_debut: date | None = None
    date_fin: date | None = None
    statut: StatutProjet | None = None
    budget: float | None = Field(default=None, ge=0)


class ProjetResponse(BaseModel):
    id: UUID
    marche_id: UUID | None = None
    tdr_id: UUID | None = None
    client_id: UUID | None = None
    titre: str
    date_debut: date | None = None
    date_fin: date | None = None
    statut: StatutProjet
    budget: float | None = None
    duree_totale_jours: int | None = None
    nombre_modules: int | None = None
    formateur_principal_id: UUID | None = None
    salle_principale_id: UUID | None = None
    resume_hebdomadaire: dict | None = None
    notes: list[str] | None = None

    model_config = {"from_attributes": True}


class FormateurCreate(BaseModel):
    nom: str = Field(..., min_length=1)
    prenom: str | None = None
    email: str | None = None
    specialite: str | None = None
    tarif_journalier: float | None = Field(default=None, ge=0)
    disponible: bool = True
    commentaire: str | None = None


class FormateurUpdate(BaseModel):
    nom: str | None = Field(default=True, min_length=1)
    prenom: str | None = None
    email: str | None = None
    specialite: str | None = None
    tarif_journalier: float | None = Field(default=None, ge=0)
    disponible: bool | None = None
    commentaire: str | None = None


class FormateurResponse(BaseModel):
    id: UUID
    nom: str
    prenom: str | None = None
    email: str | None = None
    specialite: str | None = None
    tarif_journalier: float | None = None
    disponible: bool
    commentaire: str | None = None

    model_config = {"from_attributes": True}


class SalleCreate(BaseModel):
    nom: str = Field(..., min_length=1)
    adresse: str | None = None
    capacite: int | None = Field(default=None, ge=0)
    tarif_journalier: float | None = Field(default=None, ge=0)
    disponible: bool = True
    commentaire: str | None = None


class SalleUpdate(BaseModel):
    nom: str | None = Field(default=None, min_length=1)
    adresse: str | None = None
    capacite: int | None = Field(default=None, ge=0)
    tarif_journalier: float | None = Field(default=None, ge=0)
    disponible: bool | None = None
    commentaire: str | None = None


class SalleResponse(BaseModel):
    id: UUID
    nom: str
    adresse: str | None = None
    capacite: int | None = None
    tarif_journalier: float | None = None
    disponible: bool
    commentaire: str | None = None

    model_config = {"from_attributes": True}


class EDTCreate(BaseModel):
    code_session: str | None = None
    numero_jour: int | None = None
    jour_semaine: str | None = None
    date: date
    heure_debut: time | None = None
    heure_fin: time | None = None
    duree_minutes: int | None = None
    module: str | None = None
    type_activite: str | None = None
    objectifs: list[str] | None = None
    formateur_id: UUID | None = None
    salle_id: UUID | None = None


class EDTUpdate(BaseModel):
    code_session: str | None = None
    numero_jour: int | None = None
    jour_semaine: str | None = None
    date: date | None = None
    heure_debut: time | None = None
    heure_fin: time | None = None
    duree_minutes: int | None = None
    module: str | None = None
    type_activite: str | None = None
    objectifs: str | None = None
    formateur_id: UUID | None = None
    salle_id: UUID | None = None


class EDTResponse(BaseModel):
    id: UUID
    code_session: str | None = None
    numero_jour: int | None = None
    jour_semaine: str | None = None
    date: date
    heure_debut: time | None = None
    heure_fin: time | None = None
    duree_minutes: int | None = None
    module: str | None = None
    type_activite: str | None = None
    objectifs: str | None = None
    formateur_id: UUID | None = None
    salle_id: UUID | None = None

    model_config = {"from_attributes": True}


# Output LLM Agent EDT
class FormateurLLMSchema(BaseModel):
    nom: str
    specialite: str | None = None


class SalleLLMSchema(BaseModel):
    nom: str
    adresse: str | None = None


class PauseLLMSchema(BaseModel):
    heure_debut: str = Field(..., pattern=r"^\d{2}:\d{2}$")
    heure_fin: str = Field(..., pattern=r"^\d{2}:\d{2}$")
    type: str = "pause"


class SessionLLMSchema(BaseModel):
    id: str
    heure_debut: str = Field(..., pattern=r"^\d{2}:\d{2}$")
    heure_fin: str = Field(..., pattern=r"^\d{2}:\d{2}$")
    module: str
    type: str
    duree_minutes: int
    formateur: str | None = None
    salle: str | None = None
    objectifs: list[str] = []


class JourLLMSchema(BaseModel):
    numero: int
    date: str = Field(..., pattern=r"^\d{4}-:\d{2}-\d{2}$")
    jour_semaine: str
    sessions: list[SessionLLMSchema] = []
    pauses: list[PauseLLMSchema] = []


class ResumeHebdomadaireSchema(BaseModel):
    total_heures: float
    total_sessions: int
    modules_couverts: int
    charge_journaliere_moyenne: float


class EDTGeneratorOutput(BaseModel):
    """Contrat d'interface strict pour la sortie du pipeline IA"""
    titre_formation: str
    duree_totale_jours: int
    nombre_modules: int
    formateur: FormateurLLMSchema
    salle: SalleLLMSchema
    jours: list[JourLLMSchema]
    resume_hebdomadaire: ResumeHebdomadaireSchema
    notes: list[str] = Field(default_factory=list)