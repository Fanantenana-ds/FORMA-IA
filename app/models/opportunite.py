import uuid
from datetime import datetime, timezone
from enum import Enum

from sqlalchemy import Column, String, DateTime, Enum as SqlEnum, Float, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.database import Base

class SourceOpportunite(str, Enum):
    TEXTE = "TEXTE"
    PDF = "PDF"
    URL = "URL"

class Domaine(str, Enum):
    DEVOPS = "DEVOPS"
    DEVELOPPEMENT = "DEVELOPPEMENT"
    IA = "IA"
    DATA = "DATA"
    BUREAUTIQUE = "BUREAUTIQUE"
    AUTRE = "AUTRE"

class StatutOpportunite(str, Enum):
    EN_ATTENTE = "EN_ATTENTE"
    ANALYSEE = "ANALYSEE"
    ARCHIVEE = "ARCHIVEE"

class Opportunite(Base):
    __tablename__ = "opportunites"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source = Column(SqlEnum(SourceOpportunite), nullable=False)
    contenu = Column(Text, nullable=False)
    objet = Column(String(255))
    budget = Column(Float)
    echeance = Column(DateTime(timezone=True))
    domaine = Column(SqlEnum(Domaine))
    score_pertinente = Column( Float, default=0.0)
    statut = Column(SqlEnum(StatutOpportunite), default=StatutOpportunite.EN_ATTENTE, nullable=False)
    date_creation = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    historique_analyses = relationship("HistoriqueAnalyse", back_populates="opportunite", cascade="all, delete-orphan")