# app/models/offre.py
# ============================================================
# MODÈLE — Offre technique et financière (Étape 2 CDC)
# ============================================================

import uuid
from datetime import datetime, timezone
from enum import Enum

from sqlalchemy import Column, DateTime, Float, ForeignKey, String, Text
from sqlalchemy import Enum as SqlEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.database import Base


class StatutOffre(str, Enum):
    BROUILLON = "BROUILLON"
    EN_ATTENTE = "EN_ATTENTE"
    ENVOYEE = "ENVOYEE"
    ACCEPTEE = "ACCEPTEE"
    REFUSEE = "REFUSEE"


class Offre(Base):
    __tablename__ = "offres"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Liens optionnels vers les autres entités
    opportunite_id = Column(UUID(as_uuid=True), ForeignKey("opportunites.id", ondelete="SET NULL"), nullable=True)
    tdr_document_id = Column(UUID(as_uuid=True), ForeignKey("documents.id", ondelete="SET NULL"), nullable=True)

    # Identification
    titre = Column(String(255), nullable=False)
    client = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)

    # Contenu IA (généré par /ia/offres/generer-technique et /ia/offres/generer-financiere)
    trame_technique = Column(Text, nullable=True)
    trame_financiere = Column(Text, nullable=True)

    # Montants
    montant_ht = Column(Float, nullable=True)
    tva_taux = Column(Float, nullable=False, default=20.0)

    @property
    def montant_ttc(self) -> float:
        if self.montant_ht is None:
            return 0.0
        return round(self.montant_ht * (1 + self.tva_taux / 100), 2)

    # Workflow
    statut = Column(SqlEnum(StatutOffre), nullable=False, default=StatutOffre.BROUILLON)
    date_creation = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    date_modification = Column(DateTime(timezone=True), onupdate=lambda: datetime.now(timezone.utc), nullable=True)

    # Relations
    opportunite = relationship("Opportunite")
