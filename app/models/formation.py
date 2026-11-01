import uuid
from datetime import UTC, datetime, timezone
from enum import Enum

from sqlalchemy import Column, Date, DateTime, ForeignKey, Integer, String
from sqlalchemy import Enum as sqlEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship

from app.database import Base
from app.models.tenant import TenantOwned


class StatutPresence(str, Enum):
    PRESENT = "PRESENT"
    ABSENT = "ABSENT"
    RETARD = "RETARD"
    EXCUSE = "EXCUSE"

class SourcePresence(str, Enum):
    MANUEL = "MANUEL"
    GOOGLE_FORMS = "GOOGLE_FORMS"

class Session(TenantOwned, Base):
    __tablename__ = "sessions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    titre = Column(String(50), nullable=False)
    formation_code = Column(String(50), nullable=True)
    client = Column(String(50), nullable=True)
    lieu = Column(String(200), nullable=True)
    nb_participants_max = Column(Integer, nullable=True)
    date_debut = Column(Date, nullable=False)
    date_fin = Column(Date, nullable=False)
    formateur_id = Column(UUID(as_uuid=True), ForeignKey("formateurs.id", ondelete="SET NULL"), nullable=True)
    opportunite_id = Column(UUID(as_uuid=True), ForeignKey("opportunites.id", ondelete="SET NULL"), nullable=True, index=True)
    date_creation = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False)

    seances = relationship("Seance", back_populates="session", cascade="all, delete-orphan")
    inscriptions = relationship("Inscription", back_populates="session", cascade="all, delete-orphan")

class Seance(TenantOwned, Base):
    __tablename__ = "seances"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id = Column(UUID(as_uuid=True), ForeignKey("sessions.id"), nullable=False)
    date = Column(Date, nullable=False)
    duree = Column(String(25), nullable=False)
    theme = Column(String(500), nullable=False)
    heure_debut = Column(String(5), nullable=True)
    heure_fin = Column(String(5), nullable=True)
    formateur_id = Column(UUID(as_uuid=True), ForeignKey("formateurs.id", ondelete="SET NULL"), nullable=True)

    session = relationship("Session", back_populates="seances")
    presences = relationship("Presence", back_populates="seance", cascade="all, delete-orphan")

class Participant(TenantOwned, Base):
    __tablename__ = "participants"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    nom = Column(String(50), nullable=False)
    prenom = Column(String(50), nullable=True)
    email = Column(String(200), nullable=True)
    entreprise = Column(String(100), nullable=True)

    presences = relationship("Presence", back_populates="participant", cascade="all, delete-orphan")
    inscriptions = relationship("Inscription", back_populates="participant", cascade="all, delete-orphan")

class Inscription(TenantOwned, Base):
    __tablename__ = "inscriptions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id = Column(UUID(as_uuid=True), ForeignKey("sessions.id"), nullable=False)
    participant_id = Column(UUID(as_uuid=True), ForeignKey("participants.id"), nullable=False)
    poste = Column(String(100), nullable=True)
    date_inscription = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC))
    reponses_positionnement = Column(JSONB, nullable=True)
    score_positionnement = Column(Integer, nullable=True)
    niveau_initial = Column(String(30), nullable=True)
    reponses_test_final = Column(JSONB, nullable=True)
    score_test_final = Column(Integer, nullable=True)
    niveau_final = Column(String(30), nullable=True)
    reponses_satisfaction = Column(JSONB, nullable=True)
    score_satisfaction = Column(Integer, nullable=True)  # note moyenne sur 5
    date_evaluation_finale = Column(DateTime(timezone=True), nullable=True)

    session = relationship("Session", back_populates="inscriptions")
    participant = relationship("Participant", back_populates="inscriptions")

class Presence(TenantOwned, Base):
    __tablename__ = "presences"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    seance_id = Column(UUID(as_uuid=True), ForeignKey("seances.id"), nullable=False)
    participant_id = Column(UUID(as_uuid=True), ForeignKey("participants.id"), nullable=False)
    statut = Column(sqlEnum(StatutPresence), nullable=False)
    source = Column(sqlEnum(SourcePresence), default=SourcePresence.MANUEL, nullable=False)
    heure_arrivee = Column(String(5), nullable=True)
    motif_absence = Column(String(500), nullable=True)

    seance = relationship("Seance", back_populates="presences")
    participant = relationship("Participant", back_populates="presences")
