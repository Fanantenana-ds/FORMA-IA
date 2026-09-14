import uuid
from datetime import date as date_type, datetime, timezone
from enum import Enum

from sqlalchemy import Column, String, Float, Date, DateTime, ForeignKey, Enum as SqlEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.database import Base


class StatutFacture(str, Enum):
    EMISE = "EMISE"
    PARTIELLEMENT_PAYEE = "PARTIELLEMENT_PAYEE"
    PAYEE = "PAYEE"
    EN_RETARD = "EN_RETARD"


class Facture(Base):
    __tablename__ = "factures"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    numero = Column(String(50), nullable=False, unique=True)
    client = Column(String(50), nullable=False)
    montant = Column(Float, nullable=False)
    tva_taux = Column(Float, nullable=False, default=20.0)
    statut = Column(SqlEnum(StatutFacture), default=StatutFacture.EMISE, nullable=False)
    date_emission = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    date_echeance = Column(Date, nullable=True)

    paiements = relationship("Paiement", back_populates="facture", cascade="all, delete-orphan")

    @property
    def montant_ttc(self) -> float:
        return round(self.montant * (1 + self.tva_taux / 100), 2)


class Paiement(Base):
    __tablename__ = "paiements"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    facture_id = Column(UUID(as_uuid=True), ForeignKey("factures.id"), nullable=False)
    montant = Column(Float, nullable=False)
    date = Column(Date, nullable=False)
    mode = Column(String(20), nullable=True)

    facture = relationship("Facture", back_populates="paiements")