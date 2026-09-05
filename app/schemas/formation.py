from datetime import date, datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field

from app.models.formation import StatutPresence, SourcePresence

class SessionCreate(BaseModel):
    titre: str = Field(..., min_length=1)
    client: Optional[str] = None
    date_debut: date
    date_fin: Optional[date] = None
    formateur_id: Optional[UUID] = None

class SessionResponse(BaseModel):
    id: UUID
    titre: str
    client: Optional[str] = None
    date_debut: date
    date_fin: Optional[date] = None
    formateur_id: Optional[UUID] = None
    date_creation: datetime

    model_config = {"from_attributes": True}

class SeanceCreate(BaseModel):
    date: date
    duree: Optional[str] = None
    theme: Optional[str] = None

class SeanceResponse(BaseModel):
    id: UUID
    session_id: UUID
    date: date
    duree: Optional[str] = None
    theme: Optional[str] = None

    model_config = {"from_attributes": True}

class ParticipantCreate(BaseModel):
    nom: str = Field(..., min_length=1)
    email: Optional[str] = None
    entreprise: Optional[str] = None

class ParticipantResponse(BaseModel):
    id: UUID
    nom: str
    email: Optional[str] = None
    entreprise: Optional[str] = None

    model_config = {"from_attributes": True}

class PresenceCreate(BaseModel):
    participant_id: UUID
    statut: StatutPresence
    source: SourcePresence = SourcePresence.MANUEL

class PresenceResponse(BaseModel):
    id: UUID
    participant_id: UUID
    statut: StatutPresence
    source: SourcePresence

    model_config = {"from_attributes": True}