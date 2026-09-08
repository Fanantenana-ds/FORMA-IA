# app/models/opportunity.py
# ============================================================
# MODÈLE DE DONNÉES — OPPORTUNITÉS
# ============================================================
# Ce fichier définit la table PostgreSQL pour stocker
# les opportunités commerciales détectées par M1.
# ============================================================

from sqlalchemy import Column, Integer, String, Float, DateTime, Text, Enum as SQLEnum, ARRAY
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.sql import func
import enum

Base = declarative_base()

# --- ENUM DES DOMAINES ---
class DomainEnum(str, enum.Enum):
    """Domaines d'activité possibles pour une opportunité"""
    IA = "ia"
    DEVOPS = "devops"
    DATA = "data"
    DEVELOPPEMENT = "developpement"
    BUREAUTIQUE = "bureautique"
    AUTRE = "autre"

# --- ENUM DES STATUTS ---
class StatusEnum(str, enum.Enum):
    """Statuts de traitement d'une opportunité"""
    PENDING = "pending"              # En attente d'analyse
    ANALYSING = "analysing"          # En cours d'analyse
    VALIDATED = "validated"          # Validé automatiquement
    TO_REVIEW = "to_review"          # Validation humaine requise
    REJECTED = "rejected"            # Rejeté
    ARCHIVED = "archived"            # Archivé

# --- CLASSE OPPORTUNITY ---
class Opportunity(Base):
    """Table des opportunités commerciales"""
    __tablename__ = "opportunities"

    # === IDENTIFIANT ===
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)

    # === INFORMATIONS PRINCIPALES ===
    title = Column(String(500), nullable=False, index=True)
    description = Column(Text, nullable=True)

    # === SOURCE ===
    source = Column(String(200), nullable=True)
    url = Column(Text, nullable=True)

    # === DATES ===
    publication_date = Column(DateTime, nullable=True)
    deadline = Column(DateTime, nullable=True)

    # === ORGANISME ===
    organizer = Column(String(200), nullable=True)

    # === FINANCES ===
    budget = Column(String(100), nullable=True)

    # === ANALYSE IA ===
    domain = Column(SQLEnum(DomainEnum), nullable=True, index=True)
    summary = Column(Text, nullable=True)
    score = Column(Float, nullable=True, index=True)          # 0-100
    confidence = Column(Float, nullable=True)                 # 0-1

    # === STATUT ===
    status = Column(SQLEnum(StatusEnum), default=StatusEnum.PENDING, index=True)
    flags = Column(ARRAY(String), default=[])

    # === TIMESTAMPS ===
    analysis_date = Column(DateTime, nullable=True)
    created_at = Column(DateTime, server_default=func.now(), index=True)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    # === MÉTADONNÉES ===
    reason = Column(Text, nullable=True)  # Raison du score
    reviewed_by = Column(String(100), nullable=True)  # Qui a validé

    def __repr__(self):
        return f"<Opportunity(id={self.id}, title='{self.title[:30]}...', score={self.score})>"