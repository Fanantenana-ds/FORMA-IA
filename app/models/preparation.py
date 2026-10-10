import uuid
from datetime import date as date_type
from datetime import time as time_type
from enum import Enum

from sqlalchemy import JSON, Boolean, Column, Date, Float, ForeignKey, Integer, String, Text, Time
from sqlalchemy import Enum as SqlEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.database import Base
from app.models.rh import Formateur


class StatutProjet(str, Enum):
    BROUILLON = "BROUILLON"
    EN_COURS = "EN_COURS"
    TERMINE = "TERMINE"
    ANNULE = "ANNULER"


class Projet(Base):
    __tablename__ = "projets"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    marche_id = Column(UUID(as_uuid=True), ForeignKey("opportunites.id"), nullable=True)
    tdr_id = Column(UUID(as_uuid=True), ForeignKey("documents.id"), nullable=True)
    client_id = Column(UUID(as_uuid=True), nullable=True)
    date_debut = Column(Date, nullable=True)
    date_fin = Column(Date, nullable=True)
    statut = Column(SqlEnum(StatutProjet), default=StatutProjet.BROUILLON, nullable=False)
    budget = Column(Float, nullable=True)

    duree_totale_jours = Column(Integer, nullable=True)
    nombre_modules = Column(Integer, nullable=True)
    formateur_principal_id = Column(UUID(as_uuid=True), ForeignKey("formateurs.id"), nullable=True)
    salle_principale_id = Column(UUID(as_uuid=True), ForeignKey("salles.id"), nullable=True)
    resume_hebdomadaire = Column(JSON, nullable=True)
    notes = Column(JSON, nullable=True)


    formateur_principal = relationship("Formateur", foreign_keys=[formateur_principal_id])
    salle_principale = relationship("Salle", foreign_keys=[salle_principale_id])
    edts = relationship("EDT", back_populates="projet", cascade="all, delete-orphan")
    budget_formation = relationship("BudgetFormation", back_populates="projet", uselist=False, cascade="all, delete-orphan")


class Salle(Base):
    __tablename__ = "salles"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    nom = Column(String(30), nullable=False)
    adresse = Column(String(50), nullable=True)
    capacite = Column(Integer, nullable=True)
    tarif_journalier = Column(Float, nullable=True)
    disponible = Column(Boolean, default=True, nullable=False)
    commentaire = Column(Text, nullable=True)

    edts = relationship("EDT", back_populates="salle", foreign_keys="EDT.salle_id")


class EDT(Base):
    __tablename__ = "edt_sessions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    projet_id = Column(UUID(as_uuid=True), ForeignKey("projets.id"), nullable=False)

    # Métadonnées de session / pause issues du JSON IA
    code_session = Column(String(50), nullable=True)
    numero_jour = Column(Integer, nullable=True)
    jour_semaine = Column(String(8), nullable=True)

    date = Column(Date, nullable=False)
    heure_debut = Column(Time, nullable=True)
    heure_fin = Column(Time, nullable=True)
    duree_minutes = Column(Integer, nullable=True)

    module = Column(String(20), nullable=True)
    type_activite = Column(String(20), nullable=True)
    objectifs = Column(JSON, nullable=True)

    formateur_id = Column(UUID(as_uuid=True), ForeignKey("formateurs.id"), nullable=True)
    salle_id = Column(UUID(as_uuid=True), ForeignKey("salles.id"), nullable=True)

    projet = relationship("Projet")
    formateur = relationship("Formateur", back_populates="edts", foreign_keys=[formateur_id])
    salle = relationship("Salle", back_populates="edts", foreign_keys=[salle_id])


class BudgetFormation(Base):
    __tablename__ = "budgets_formation"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    projet_id = Column(UUID(as_uuid=True), ForeignKey("projets.id"), nullable=False, unique=True)
    cout_formateur = Column(Float, default=0.0, nullable=False)
    cout_salle = Column(Float, default=0.0, nullable=False)
    cout_support = Column(Float, default=0.0, nullable=False)
    cout_total = Column(Float, default=0.0, nullable=False)
    valide_par = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)

    projet = relationship("Projet", back_populates="budget_formation")