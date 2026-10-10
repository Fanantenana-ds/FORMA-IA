import datetime as _dt
from datetime import date, datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field

from app.models.formation import SourcePresence, StatutPresence


class SessionCreate(BaseModel):
    titre: str = Field(..., min_length=1)
    client: str | None = None
    date_debut: date
    date_fin: date | None = None
    formateur_id: UUID | None = None


class SessionUpdate(BaseModel):
    """Mise à jour partielle d'une session (tous les champs sont optionnels)."""
    titre: str | None = Field(default=None, min_length=1)
    client: str | None = None
    date_debut: date | None = None
    date_fin: date | None = None
    formateur_id: UUID | None = None


class SessionResponse(BaseModel):
    id: UUID
    titre: str
    client: str | None = None
    date_debut: date
    date_fin: date | None = None
    formateur_id: UUID | None = None
    date_creation: datetime

    model_config = {"from_attributes": True}

class SeanceCreate(BaseModel):
    date: date
    duree: str | None = None
    theme: str | None = None

class SeanceUpdate(BaseModel):
    """Mise à jour partielle d'une séance (tous les champs sont optionnels)."""
    # Le champ "date" masque le type dans le corps de classe : passer par le module.
    date: _dt.date | None = None
    duree: str | None = None
    theme: str | None = None

class SeanceResponse(BaseModel):
    id: UUID
    session_id: UUID
    date: date
    duree: str | None = None
    theme: str | None = None

    model_config = {"from_attributes": True}

class ParticipantCreate(BaseModel):
    nom: str = Field(..., min_length=1)
    email: str | None = None
    entreprise: str | None = None

class ParticipantUpdate(BaseModel):
    """Mise à jour partielle d'un participant (tous les champs sont optionnels)."""
    nom: str | None = Field(default=None, min_length=1)
    email: str | None = None
    entreprise: str | None = None

class ParticipantResponse(BaseModel):
    id: UUID
    nom: str
    email: str | None = None
    entreprise: str | None = None

    model_config = {"from_attributes": True}

class PresenceCreate(BaseModel):
    participant_id: UUID
    statut: StatutPresence
    source: SourcePresence = SourcePresence.MANUEL

class PresenceUpdate(BaseModel):
    """Correction du statut d'une présence (PRESENT / ABSENT / EXCUSE)."""
    statut: StatutPresence

class PresenceResponse(BaseModel):
    id: UUID
    seance_id: UUID
    participant_id: UUID
    statut: StatutPresence
    source: SourcePresence

    model_config = {"from_attributes": True}


class InscriptionCreate(BaseModel):
    """Inscrit un participant existant à une session."""
    participant_id: UUID


class InscriptionResponse(BaseModel):
    id: UUID
    session_id: UUID
    participant_id: UUID

    model_config = {"from_attributes": True}