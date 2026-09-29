from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.models.formation import SourcePresence, StatutPresence


class SessionCreate(BaseModel):
    titre: str = Field(..., min_length=1)
    client: str | None = None
    date_debut: date
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

class PresenceResponse(BaseModel):
    id: UUID
    participant_id: UUID
    statut: StatutPresence
    source: SourcePresence

    model_config = {"from_attributes": True}