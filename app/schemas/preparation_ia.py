from typing import List, Optional, Dict, Any, Literal
from pydantic import BaseModel, Field


# ============================================================
# EDT — SESSIONS
# ============================================================

SessionType = Literal["cours", "atelier", "projet", "evaluation", "pause"]


class EDTSession(BaseModel):
    """Une session dans l'emploi du temps."""
    id: str = Field(..., description="ID unique (ex: s_01_01)")
    heure_debut: str = Field(..., description="Heure début (HH:MM)")
    heure_fin: str = Field(..., description="Heure fin (HH:MM)")
    module: str = Field(..., description="Titre du module")
    type: SessionType = Field(..., description="Type d'activité")
    duree_minutes: int = Field(..., ge=0, description="Durée en minutes")
    formateur: Optional[str] = None
    salle: Optional[str] = None
    objectifs: List[str] = Field(default_factory=list)


class EDTPause(BaseModel):
    """Une pause dans l'emploi du temps."""
    heure_debut: str = Field(..., description="Heure début (HH:MM)")
    heure_fin: str = Field(..., description="Heure fin (HH:MM)")
    type: Literal["pause", "dejeuner", "autre"] = "pause"


class EDTJour(BaseModel):
    """Une journée de formation."""
    numero: int = Field(..., ge=1, description="Numéro du jour (1, 2, ...)")
    date: str = Field(..., description="Date (YYYY-MM-DD)")
    jour_semaine: Optional[str] = None
    sessions: List[EDTSession] = Field(default_factory=list)
    pauses: List[EDTPause] = Field(default_factory=list)


class EDTFormateur(BaseModel):
    """Informations sur le formateur."""
    nom: str
    specialite: Optional[str] = None


class EDTSalle(BaseModel):
    """Informations sur la salle."""
    nom: str
    adresse: Optional[str] = None


class EDTResume(BaseModel):
    """Résumé de l'EDT."""
    total_heures: float = Field(..., ge=0)
    total_sessions: int = Field(..., ge=0)
    modules_couverts: int = Field(..., ge=0)
    charge_journaliere_moyenne: float = Field(..., ge=0)


class EDTResponse(BaseModel):
    """
    Réponse complète du EDTGeneratorService.

    Contient l'emploi du temps complet d'une formation.
    """
    success: bool = True
    titre_formation: str
    duree_totale_jours: int = Field(..., ge=1)
    nombre_modules: int = Field(..., ge=0)

    formateur: Optional[EDTFormateur] = None
    salle: Optional[EDTSalle] = None

    jours: List[EDTJour] = Field(default_factory=list)
    resume_hebdomadaire: Optional[EDTResume] = None
    notes: List[str] = Field(default_factory=list)

    # Métadonnées
    metadata: Optional[Dict[str, Any]] = None


# ============================================================
# BUDGET PRÉVISIONNEL
# ============================================================

class CoutDetail(BaseModel):
    """Détail d'un poste de coût."""
    libelle: str = Field(..., description="Libellé du poste")
    base: Optional[float] = Field(None, description="Base de calcul (tarif, forfait)")
    quantite: Optional[int] = Field(None, description="Quantité (jours, participants)")
    montant: int = Field(..., ge=0, description="Montant total en MGA")
    description: Optional[str] = None


class BudgetPrevisionnel(BaseModel):
    """
    Budget prévisionnel calculé par Python.

    ⚠️ Ces montants sont CALCULÉS par Python (pas par LLM).
    """
    devise: str = Field("MGA", description="Devise")

    # Détails
    cout_formateur: int = Field(..., ge=0, description="Coût formateur total")
    cout_salle: int = Field(..., ge=0, description="Coût salle total")
    cout_supports: int = Field(..., ge=0, description="Coût supports total")
    cout_logistique: int = Field(0, ge=0, description="Coût logistique")
    cout_administration: int = Field(0, ge=0, description="Coût administration")

    cout_total: int = Field(..., ge=0, description="Coût total prévisionnel")

    # Détails par poste (optionnel)
    details: List[CoutDetail] = Field(default_factory=list)


# ============================================================
# PRÉPARATION COMPLÈTE (Budget + EDT)
# ============================================================

class PreparationCompleteData(BaseModel):
    """Données complètes de la préparation."""
    budget: BudgetPrevisionnel
    edt: EDTResponse


class PreparationCompleteResponse(BaseModel):
    """
    Réponse complète de l'orchestrateur Préparation.

    Combine :
        - Budget prévisionnel (Python pur)
        - EDT (LLM)
        - HITL review
    """
    success: bool = True

    # Identifiants
    projet_id: Optional[int] = None
    offre_id: Optional[int] = None
    client_id: Optional[int] = None

    # Résultats
    budget: Optional[BudgetPrevisionnel] = None
    edt: Optional[EDTResponse] = None

    # HITL
    review_id: Optional[str] = Field(None, alias="_review_id")
    review_status: Optional[str] = Field(None, alias="_review_status")

    # Métadonnées
    metadata: Optional[Dict[str, Any]] = None

    class Config:
        populate_by_name = True


# ============================================================
# SCHÉMAS DE REQUÊTE (pour les routes API)
# ============================================================

class CalculateBudgetRequest(BaseModel):
    """Corps de la requête pour calculer le budget."""
    formateur_info: Dict[str, Any] = Field(
        ...,
        description="Infos formateur (nom, tarif_journalier)",
    )
    salle_info: Dict[str, Any] = Field(
        ...,
        description="Infos salle (nom, tarif_journalier)",
    )
    nb_jours: int = Field(..., ge=1, le=30, description="Nombre de jours")
    nb_participants: int = Field(..., ge=1, le=500, description="Nombre de participants")

    class Config:
        json_schema_extra = {
            "example": {
                "formateur_info": {
                    "nom": "M. RANAIVOSOA S.",
                    "tarif_journalier": 500000,
                },
                "salle_info": {
                    "nom": "Salle A",
                    "tarif_journalier": 200000,
                },
                "nb_jours": 2,
                "nb_participants": 20,
            }
        }


class GenerateEDTRequest(BaseModel):
    """Corps de la requête pour générer l'EDT."""
    titre_formation: str = Field(..., min_length=3)
    modules: List[Dict[str, Any]] = Field(
        ...,
        description="Liste des modules (titre, duree)",
    )
    dates: List[str] = Field(
        ...,
        description="Dates des jours de formation (YYYY-MM-DD)",
    )
    formateur: Optional[Dict[str, Any]] = Field(
        None,
        description="Infos formateur (nom, specialite)",
    )
    salle: Optional[Dict[str, Any]] = Field(
        None,
        description="Infos salle (nom, adresse)",
    )

    class Config:
        json_schema_extra = {
            "example": {
                "titre_formation": "Introduction à l'IA",
                "modules": [
                    {"titre": "Introduction", "duree": "3h"},
                    {"titre": "Apprentissage", "duree": "3h"},
                ],
                "dates": ["2026-10-15", "2026-10-16"],
                "formateur": {"nom": "M. RANAIVOSOA", "specialite": "IA"},
                "salle": {"nom": "Salle A", "adresse": "Antananarivo"},
            }
        }


class GeneratePreparationCompleteRequest(BaseModel):
    """Corps de la requête pour générer la préparation complète."""
    offre_data: Dict[str, Any] = Field(
        ...,
        description="Données de l'offre approuvée (M3)",
    )
    projet_info: Dict[str, Any] = Field(
        ...,
        description="Informations du projet (client, participants)",
    )
    ressources: Dict[str, Any] = Field(
        ...,
        description="Ressources : formateur + salle",
    )
    options: Dict[str, Any] = Field(
        default_factory=dict,
        description="Options (date_debut, date_fin)",
    )

    class Config:
        json_schema_extra = {
            "example": {
                "offre_data": {
                    "reference": "ALT-OFF-TECH-2026-0001",
                    "titre": "Introduction à l'IA",
                    "duree_jours": 2,
                    "modules": [
                        {"titre": "Introduction", "duree": "3h"},
                        {"titre": "Apprentissage", "duree": "3h"},
                    ],
                },
                "projet_info": {
                    "id": 1,
                    "marche_id": 1,
                    "client": "Ministère de l'Éducation",
                    "nb_participants": 20,
                },
                "ressources": {
                    "formateur": {
                        "nom": "M. RANAIVOSOA S.",
                        "tarif_journalier": 500000,
                        "specialite": "IA",
                    },
                    "salle": {
                        "nom": "Salle A",
                        "tarif_journalier": 200000,
                        "adresse": "Antananarivo",
                    },
                },
                "options": {
                    "date_debut": "2026-10-15",
                    "date_fin": "2026-10-16",
                },
            }
        }


class RegeneratePreparationRequest(BaseModel):
    """Corps de la requête pour régénérer une préparation."""
    review_id: str = Field(..., description="ID du review rejeté")
    feedback: str = Field(..., min_length=10, description="Feedback humain")