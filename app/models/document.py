import uuid
from datetime import datetime, timezone
from enum import Enum

from sqlalchemy import Column, String, DateTime, Text, ForeignKey, Float, Enum as SQLEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.database import Base

class TypeDocument(str, Enum):
    TDR = "TDR"
    OFFRE = "OFFRE"
    ATTESTATION = "ATTESTATION"

class FormatExport(str, Enum):
    PDF = "PDF"
    DOCX = "DOCX"

class StatutValidation(str, Enum):
    EN_ATTENTE = "EN_ATTENTE"
    VALIDE = "VALIDE"
    REJETE = "REJETE"

class Document(Base):
    __tablename__ = "documents"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    type = Column(SQLEnum(TypeDocument), nullable=False)
    format_export = Column(SQLEnum(FormatExport), nullable=True)
    contenu = Column(Text, nullable=True)
    statut_validation = Column(SQLEnum(StatutValidation), nullable=False, default=StatutValidation.EN_ATTENTE)
    valide_par = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    date_generation = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    date_validation = Column(DateTime(timezone=True), nullable=True)

    client = Column(String(255), nullable=True)
    objectifs = Column(Text, nullable=True)

    opportunite_id = Column(UUID(as_uuid=True), ForeignKey("opportunites.id"), nullable=True)
    montant = Column(Float, nullable=True)

    session_id = Column(UUID(as_uuid=True), ForeignKey("sessions.id"), nullable=True)
    participant_id = Column(UUID(as_uuid=True), ForeignKey("participants.id"), nullable=True)
    numero_unique = Column(String(50), nullable=True, unique=True)

    opportunite = relationship("Opportunite")

    __mapper_args__ = {
        "polymorphic_on": type,
        "polymorphic_identity": None,
    }

class TDR(Document):
    __mapper_args__ = {
        "polymorphic_identity": TypeDocument.TDR,
    }

class Offre(Document):
    __mapper_args__ = {
        "polymorphic_identity": TypeDocument.OFFRE,
    }

class Attestation(Document):
    __mapper_args__ = {
        "polymorphic_identity": TypeDocument.ATTESTATION,
    }