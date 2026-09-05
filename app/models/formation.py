import uuid
from datetime import date as date_type, datetime, timezone
from enum import Enum

from sqlalchemy import Column, String, Date, DateTime, ForeignKey, Enum as sqlEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.database import Base

class StatutPresence(str, Enum):
    PRESENT = "PRESENT"
    ABSENT = "ABSENT"
    EXCUSE = "EXCUSE"

class SourcePresence(str, Enum):
    MANUEL = "MANUEL"
    GOOGLE_FORMS = "GOOGLE_FORMS"

class Session(Base):
    __tablename__ = "sessions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    titre = Column(String(50), nullable=False)
    client = Column(String(50), nullable=True)
    date_debut = Column(Date, nullable=False)
    date_fin = Column(Date, nullable=False)
    formateur_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    date_creation = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    seances = relationship("Seance", back_populates="session", cascade="all, delete-orphan")
    inscriptions = relationship("Inscription", back_populates="session", cascade="all, delete-orphan")

class Seance(Base):
    __tablename__ = "seances"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id = Column(UUID(as_uuid=True), ForeignKey("sessions.id"), nullable=False)
    date = Column(Date, nullable=False)
    duree = Column(String(25), nullable=False)
    theme = Column(String(100), nullable=False)

    session = relationship("Session", back_populates="seances")
    presences = relationship("Presence", back_populates="seance", cascade="all, delete-orphan")

class Participant(Base):
    __tablename__ = "participants"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    nom = Column(String(50), nullable=False)
    email = Column(String(30), nullable=True)
    entreprise = Column(String(30), nullable=True)

    presences = relationship("Presence", back_populates="participant")
    inscriptions = relationship("Inscription", back_populates="participant")

class Inscription(Base):
    __tablename__ = "inscriptions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id = Column(UUID(as_uuid=True), ForeignKey("sessions.id"), nullable=False)
    participant_id = Column(UUID(as_uuid=True), ForeignKey("participants.id"), nullable=False)

    session = relationship("Session", back_populates="inscriptions")
    participant = relationship("Participant", back_populates="inscriptions")

class Presence(Base):
    __tablename__ = "presences"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    seance_id = Column(UUID(as_uuid=True), ForeignKey("seances.id"), nullable=False)
    participant_id = Column(UUID(as_uuid=True), ForeignKey("participants.id"), nullable=False)
    statut = Column(sqlEnum(StatutPresence), nullable=False)
    source = Column(sqlEnum(SourcePresence), default=SourcePresence.MANUEL, nullable=False)

    seance = relationship("Seance", back_populates="presences")
    participant = relationship("Participant", back_populates="presences")