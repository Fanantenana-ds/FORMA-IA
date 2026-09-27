import uuid
from datetime import datetime, timezone
from enum import Enum

from sqlalchemy import Column, String, Float, Boolean, DateTime, ForeignKey, Text, Enum as SqlEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.database import Base


class StatutFormateur(str, Enum):
    DISPONIBLE  = "DISPONIBLE"
    OCCUPE      = "OCCUPE"
    INACTIF     = "INACTIF"


class DecisionPreselection(str, Enum):
    RETENU       = "RETENU"
    A_DISCUTER   = "A_DISCUTER"
    NON_RETENU   = "NON_RETENU"


class DecisionEntretien(str, Enum):
    RECRUTER         = "RECRUTER"
    APPROFONDIR      = "APPROFONDIR"
    NE_PAS_RECRUTER  = "NE_PAS_RECRUTER"


class RecommandationEvaluation(str, Enum):
    OUI         = "OUI"
    CONDITIONNEL = "CONDITIONNEL"
    NON         = "NON"


# ============================================================
# FORMATEUR — prestataire externe récurrent
# ============================================================

class Formateur(Base):
    __tablename__ = "formateurs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    nom = Column(String(100), nullable=False)
    prenom = Column(String(100), nullable=True)
    email = Column(String(200), nullable=True)
    telephone = Column(String(30), nullable=True)
    adresse = Column(String(300), nullable=True)
    specialite = Column(String(200), nullable=True)
    tarif_journalier = Column(Float, nullable=True)
    statut = Column(
        SqlEnum(StatutFormateur),
        default=StatutFormateur.DISPONIBLE,
        nullable=False,
    )
    # enrichi par A5 (évaluation post-session)
    score_moyen = Column(Float, nullable=True)
    nb_sessions = Column(String(10), nullable=True)   # ex: "3"
    recommandation = Column(
        SqlEnum(RecommandationEvaluation),
        nullable=True,
    )
    notes_internes = Column(Text, nullable=True)

    date_creation = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    candidatures = relationship(
        "Candidat", back_populates="formateur", cascade="all, delete-orphan"
    )


# ============================================================
# CANDIDAT — dossier de présélection (A1) et entretien (A2)
# ============================================================

class Candidat(Base):
    __tablename__ = "candidats"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    nom = Column(String(200), nullable=False)
    poste_vise = Column(String(200), nullable=False)
    cv_texte = Column(Text, nullable=True)
    score_preselection = Column(Float, nullable=True)
    decision_preselection = Column(
        SqlEnum(DecisionPreselection),
        nullable=True,
    )
    review_id_preselection = Column(String(100), nullable=True)

    # FK vers Formateur si recrutement confirmé
    formateur_id = Column(
        UUID(as_uuid=True),
        ForeignKey("formateurs.id", ondelete="SET NULL"),
        nullable=True,
    )
    formateur = relationship("Formateur", back_populates="candidatures")

    date_creation = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    entretiens = relationship(
        "Entretien", back_populates="candidat", cascade="all, delete-orphan"
    )


# ============================================================
# ENTRETIEN — CR structuré (A2) + brouillon email (A3)
# ============================================================

class Entretien(Base):
    __tablename__ = "entretiens"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    candidat_id = Column(
        UUID(as_uuid=True),
        ForeignKey("candidats.id", ondelete="CASCADE"),
        nullable=False,
    )
    date_entretien = Column(DateTime(timezone=True), nullable=True)
    interviewers = Column(String(500), nullable=True)   # CSV
    notes_brutes = Column(Text, nullable=True)
    compte_rendu = Column(Text, nullable=True)           # JSON sérialisé
    decision = Column(SqlEnum(DecisionEntretien), nullable=True)
    review_id_entretien = Column(String(100), nullable=True)
    email_brouillon = Column(Text, nullable=True)        # JSON sérialisé
    review_id_email = Column(String(100), nullable=True)

    date_creation = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    candidat = relationship("Candidat", back_populates="entretiens")
