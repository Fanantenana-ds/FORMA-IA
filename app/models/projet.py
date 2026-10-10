# app/models/projet.py
# ============================================================
# MODÈLES — Préparation de la formation (Étape 3 CDC)
# Salle, Projet, EdtSession, BudgetFormation
# ============================================================

import uuid
from datetime import date as date_type
from datetime import datetime, time, timezone
from enum import Enum

from sqlalchemy import (
    Boolean,
    Column,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    Time,
)
from sqlalchemy import (
    Enum as SqlEnum,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.database import Base


class StatutProjet(str, Enum):
    BROUILLON = "BROUILLON"
    EN_COURS = "EN_COURS"
    VALIDE = "VALIDE"
    TERMINE = "TERMINE"
    ANNULE = "ANNULE"


# ── Salle ───────────────────────────────────────────────────

class Salle(Base):
    __tablename__ = "salles"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    nom = Column(String(100), nullable=False)
    adresse = Column(String(255), nullable=True)
    capacite = Column(Integer, nullable=True)
    tarif_journalier = Column(Float, nullable=True)
    equipements = Column(Text, nullable=True)   # texte libre : "vidéoprojecteur, climatisation…"
    disponible = Column(Boolean, nullable=False, default=True)
    date_creation = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)


# ── Projet ──────────────────────────────────────────────────

class Projet(Base):
    __tablename__ = "projets"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Liens optionnels
    opportunite_id = Column(UUID(as_uuid=True), ForeignKey("opportunites.id", ondelete="SET NULL"), nullable=True)
    offre_id = Column(UUID(as_uuid=True), ForeignKey("offres.id", ondelete="SET NULL"), nullable=True)

    titre = Column(String(100), nullable=False)
    client = Column(String(100), nullable=True)
    date_debut = Column(Date, nullable=True)
    date_fin = Column(Date, nullable=True)
    statut = Column(SqlEnum(StatutProjet), nullable=False, default=StatutProjet.BROUILLON)
    notes = Column(Text, nullable=True)
    date_creation = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    # Relations
    edt_sessions = relationship("EdtSession", back_populates="projet", cascade="all, delete-orphan")
    budget = relationship("BudgetFormation", back_populates="projet", cascade="all, delete-orphan", uselist=False)


# ── EdtSession (emploi du temps) ────────────────────────────

class EdtSession(Base):
    __tablename__ = "edt_sessions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    projet_id = Column(UUID(as_uuid=True), ForeignKey("projets.id", ondelete="CASCADE"), nullable=False)
    date = Column(Date, nullable=False)
    heure_debut = Column(Time, nullable=True)
    heure_fin = Column(Time, nullable=True)
    module = Column(String(200), nullable=True)
    formateur_id = Column(UUID(as_uuid=True), ForeignKey("formateurs.id", ondelete="SET NULL"), nullable=True)
    salle_id = Column(UUID(as_uuid=True), ForeignKey("salles.id", ondelete="SET NULL"), nullable=True)

    projet = relationship("Projet", back_populates="edt_sessions")
    salle = relationship("Salle")


# ── BudgetFormation ─────────────────────────────────────────

class BudgetFormation(Base):
    __tablename__ = "budgets_formation"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    projet_id = Column(UUID(as_uuid=True), ForeignKey("projets.id", ondelete="CASCADE"), nullable=False, unique=True)
    cout_formateur = Column(Float, nullable=False, default=0.0)
    cout_salle = Column(Float, nullable=False, default=0.0)
    cout_supports = Column(Float, nullable=False, default=0.0)
    cout_total = Column(Float, nullable=False, default=0.0)
    valide = Column(Boolean, nullable=False, default=False)
    valide_par = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    date_creation = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    projet = relationship("Projet", back_populates="budget")
