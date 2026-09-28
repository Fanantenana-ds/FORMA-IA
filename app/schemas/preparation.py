from datetime import date, time
from typing import List, Optional
from uuid import UUID
from pydantic import BaseModel, Field
from app.models.preparation import StatutProjet


class ProjetCreate(BaseModel):
    marche_id: Optional[UUID] = None
    tdr_id: Optional[UUID] = None
    client_id: Optional[UUID] = None
    titre: str = Field(..., min_length=1)
    date_debut: Optional[date] = None
    date_fin: Optional[date] = None
    budget: Optional[float] = Field(default=None, ge=0)


class ProjetUpdate(BaseModel):
    marche_id: Optional[UUID] = None
    tdr_id: Optional[UUID] = None
    client_id: Optional[UUID] = None
    titre: Optional[str] = Field(default=None, min_length=1)
    date_debut: Optional[date] = None
    date_fin: Optional[date] = None
    statut: Optional[StatutProjet] = None
    budget: Optional[float] = Field(default=None, ge=0)


class ProjetResponse(BaseModel):
    id: UUID
    marche_id: Optional[UUID] = None
    tdr_id: Optional[UUID] = None
    client_id: Optional[UUID] = None
    titre: str
    date_debut: Optional[date] = None
    date_fin: Optional[date] = None
    statut: StatutProjet
    budget: Optional[float] = None
    duree_totale_jours: Optional[int] = None
    nombre_modules: Optional[int] = None
    formateur_principal_id: Optional[UUID] = None
    salle_principale_id: Optional[UUID] = None
    resume_hebdomadaire: Optional[dict] = None
    notes: Optional[List[str]] = None

    model_config = {"from_attributes": True}


class FormateurCreate(BaseModel):
    nom: str = Field(..., min_length=1)
    prenom: Optional[str] = None
    email: Optional[str] = None
    specialite: Optional[str] = None
    tarif_journalier: Optional[float] = Field(default=None, ge=0)
    disponible: bool = True
    commentaire: Optional[str] = None


class FormateurUpdate(BaseModel):
    nom: Optional[str] = Field(default=True, min_length=1)
    prenom: Optional[str] = None
    email: Optional[str] = None
    specialite: Optional[str] = None
    tarif_journalier: Optional[float] = Field(default=None, ge=0)
    disponible: Optional[bool] = None
    commentaire: Optional[str] = None


class FormateurResponse(BaseModel):
    id: UUID
    nom: str
    prenom: Optional[str] = None
    email: Optional[str] = None
    specialite: Optional[str] = None
    tarif_journalier: Optional[float] = None
    disponible: bool
    commentaire: Optional[str] = None

    model_config = {"from_attributes": True}


class SalleCreate(BaseModel):
    nom: str = Field(..., min_length=1)
    adresse: Optional[str] = None
    capacite: Optional[int] = Field(default=None, ge=0)
    tarif_journalier: Optional[float] = Field(default=None, ge=0)
    disponible: bool = True
    commentaire: Optional[str] = None


class SalleUpdate(BaseModel):
    nom: Optional[str] = Field(default=None, min_length=1)
    adresse: Optional[str] = None
    capacite: Optional[int] = Field(default=None, ge=0)
    tarif_journalier: Optional[float] = Field(default=None, ge=0)
    disponible: Optional[bool] = None
    commentaire: Optional[str] = None


class SalleResponse(BaseModel):
    id: UUID
    nom: str
    adresse: Optional[str] = None
    capacite: Optional[int] = None
    tarif_journalier: Optional[float] = None
    disponible: bool
    commentaire: Optional[str] = None

    model_config = {"from_attributes": True}


class EDTCreate(BaseModel):
    code_session: Optional[str] = None
    numero_jour: Optional[int] = None
    jour_semaine: Optional[str] = None
    date: date
    heure_debut: Optional[time] = None
    heure_fin: Optional[time] = None
    duree_minutes: Optional[int] = None
    module: Optional[str] = None
    type_activite: Optional[str] = None
    objectifs: Optional[List[str]] = None
    formateur_id: Optional[UUID] = None
    salle_id: Optional[UUID] = None


class EDTUpdate(BaseModel):
    code_session: Optional[str] = None
    numero_jour: Optional[int] = None
    jour_semaine: Optional[str] = None
    date: Optional[date] = None
    heure_debut: Optional[time] = None
    heure_fin: Optional[time] = None
    duree_minutes: Optional[int] = None
    module: Optional[str] = None
    type_activite: Optional[str] = None
    objectifs: Optional[str] = None
    formateur_id: Optional[UUID] = None
    salle_id: Optional[UUID] = None


class EDTResponse(BaseModel):
    id: UUID
    code_session: Optional[str] = None
    numero_jour: Optional[int] = None
    jour_semaine: Optional[str] = None
    date: date
    heure_debut: Optional[time] = None
    heure_fin: Optional[time] = None
    duree_minutes: Optional[int] = None
    module: Optional[str] = None
    type_activite: Optional[str] = None
    objectifs: Optional[str] = None
    formateur_id: Optional[UUID] = None
    salle_id: Optional[UUID] = None

    model_config = {"from_attributes": True}


# Output LLM Agent EDT
class FormateurLLMSchema(BaseModel):
    nom: str
    specialite: Optional[str] = None


class SalleLLMSchema(BaseModel):
    nom: str
    adresse: Optional[str] = None


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
    formateur: Optional[str] = None
    salle: Optional[str] = None
    objectifs: List[str] = []


class JourLLMSchema(BaseModel):
    numero: int
    date: str = Field(..., pattern=r"^\d{4}-:\d{2}-\d{2}$")
    jour_semaine: str
    sessions: List[SessionLLMSchema] = []
    pauses: List[PauseLLMSchema] = []


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
    jours: List[JourLLMSchema]
    resume_hebdomadaire: ResumeHebdomadaireSchema
    notes: List[str] = Field(default_factory=list)