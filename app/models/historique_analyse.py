import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, String, DateTime, Float, Text, ForeignKey, Enum as SqlEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.database import Base
from app.models.opportunite import Domaine

class HistoriqueAnalyse(Base):
    __tablename__ = "historique_analyses"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    opportunite_id = Column(UUID(as_uuid=True), ForeignKey("opportunites.id"), nullable=False)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    objet = Column(String(255))
    budget = Column(Float)
    echeance = Column(DateTime(timezone=True))
    domaine = Column(SqlEnum(Domaine))
    exigences = Column(Text)
    score_pertinente = Column(Float, default=0.0)
    date_analyse = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    opportunite = relationship("Opportunite", back_populates="historique_analyses")