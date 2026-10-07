# app/schemas/rh_ia.py
# ============================================================
# SCHÉMAS — ROUTES IA M4 (Assistance RH)
# ============================================================

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class PreselectionCvRequest(BaseModel):
    cv_texte: str = Field(..., min_length=50, description="Texte brut du CV")
    criteres_poste: Dict[str, Any] = Field(
        ...,
        description=(
            "Critères du poste : domaine (str), competences (list[str]), "
            "niveau (str), experience_formation_min (str)"
        ),
        examples=[{
            "domaine": "Intelligence Artificielle",
            "competences": ["Python", "Machine Learning", "Pédagogie"],
            "niveau": "expert",
            "experience_formation_min": "2 ans",
        }],
    )


class EntretienCrRequest(BaseModel):
    notes_brutes: str = Field(
        ..., min_length=20,
        description="Notes prises pendant ou après l'entretien (texte libre)"
    )
    candidat: str = Field(..., min_length=2, description="Nom complet du candidat")
    poste: str = Field(..., min_length=2, description="Intitulé du poste / domaine")
    interviewers: Optional[List[str]] = Field(
        default=None, description="Noms des personnes présentes"
    )
    date_entretien: Optional[str] = Field(
        default=None, description="Date de l'entretien (YYYY-MM-DD)"
    )
    review_id_a1: Optional[str] = Field(
        default=None,
        description=(
            "ID review présélection A1 (ex: HITL-AM4-0066). "
            "Si fourni, le CR sera enrichi avec le score CV, les réserves "
            "et les questions d'entretien générées par A1."
        )
    )


class EmailRhRequest(BaseModel):
    type_email: str = Field(
        ...,
        description=(
            "Type d'email : ACCEPTATION | REFUS | DEMANDE_INFO | "
            "CONVOCATION | PROPOSITION_MISSION"
        ),
    )
    destinataire: str = Field(..., min_length=2, description="Nom du destinataire")
    contexte: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Informations supplémentaires (poste, mission, date, etc.)",
    )


class FormateurInfo(BaseModel):
    nom: str = Field(..., min_length=2)
    adresse: Optional[str] = None
    telephone: Optional[str] = None
    email: Optional[str] = None
    tarif_journalier: float = Field(..., gt=0, description="Tarif en MGA")


class SessionInfo(BaseModel):
    titre: str = Field(..., min_length=2)
    dates: List[str] = Field(..., min_items=1, description="Liste de dates YYYY-MM-DD")
    nb_jours: int = Field(..., ge=1)
    lieu: str = Field(default="Antananarivo")
    nb_participants: int = Field(default=0, ge=0)
    description: Optional[str] = Field(default=None)


class ContratFormateurRequest(BaseModel):
    formateur: FormateurInfo
    session: SessionInfo


class DonneesSessionM5(BaseModel):
    satisfaction: Optional[Dict[str, Any]] = Field(
        default=None,
        description=(
            "Résultats M5 satisfaction : "
            "{score_moyen, points_positifs, points_negatifs}"
        ),
    )
    presences: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Résultats M5 présences : {taux_moyen_pct, anomalies}",
    )
    rapport: Optional[str] = Field(
        default=None, description="Extrait du rapport final M5 (optionnel)"
    )


class EvaluationFormateurRequest(BaseModel):
    formateur: str = Field(..., min_length=2, description="Nom du formateur")
    session: str = Field(..., min_length=2, description="Titre de la session")
    donnees_session: DonneesSessionM5
