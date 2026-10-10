import uuid
from datetime import datetime, timezone
from enum import Enum

from sqlalchemy import Column, Date, DateTime, Float, ForeignKey, String
from sqlalchemy import Enum as SqlEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.database import Base


class StatutFacture(str, Enum):
    EMISE = "EMISE"
    PARTIELLEMENT_PAYEE = "PARTIELLEMENT_PAYEE"
    PAYEE = "PAYEE"
    EN_RETARD = "EN_RETARD"
    ANNULEE = "ANNULEE"


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
    relances = relationship("Relance", back_populates="facture", cascade="all, delete-orphan")

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


class Relance(Base):
    __tablename__ = "relances"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    facture_id = Column(UUID(as_uuid=True), ForeignKey("factures.id"), nullable=False)
    niveau = Column(String(1), nullable=False)          # "1", "2" ou "3"
    objet = Column(String(200), nullable=False)
    texte = Column(String(10000), nullable=False)
    review_id = Column(String(100), nullable=True)      # ID du review HITL approuvé
    date_creation = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    facture = relationship("Facture", back_populates="relances")