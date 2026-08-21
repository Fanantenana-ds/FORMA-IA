import uuid
from datetime import datetime
from enum import Enum

from sqlalchemy import Column, String, DateTime, Enum as SqlEnum, Float,String, Text
from sqlalchemy.dialects.postgresql import UUID

from app.database import Base

class SourceOppotunite(str, Enum):
    TEXTE = "TEXTE"
    PDF = "PDF"
    URL = "URL"

class Domaine(str, Enum):
    DEVOPS = "DEVOPS"
    DEVELOPPEMENT = "DEVELOPPEMENT"
    IA = "IA"
    DATA = "DATA"
    AUTRE = "AUTRE"

class StatutOppoetunite(str, Enum):
    EN_ATTENTE = "EN_ATTENTE"
    ANALYSEE = "ANALYSER"
    ARCHIVEE = "ARCHIVEE"

class Opportunite(Base):
    __tablename__ = "opportunites"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source = Column(SqlEnum(SourceOppotunite), nullable=False)
    contenu = Column(Text, nullable=False)
    objet = Column(String(255))
    budget = Column(Float)
    echeance = Column(DateTime)
    domaine = Column(SqlEnum(Domaine))
    score_pertinente = Column( Float, default=0.0)
    statut = Column(SqlEnum(StatutOppoetunite), default=StatutOppoetunite.EN_ATTENTE, nullable=False)
    date_creation = Column(DateTime, default=datetime.utcnow, nullable=False)