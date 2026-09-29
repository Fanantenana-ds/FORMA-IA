"""
Schémas Pydantic — Outputs IA du module M5 (Gestion des Formations).

Ces schémas sont utilisés pour VALIDER les réponses JSON produites par les
agents IA (Groq) avant de les transmettre au Backend.

⚠️ Ne pas confondre avec app/schemas/formation.py (schémas Backend).
"""

from typing import Any, Literal

from pydantic import BaseModel, Field

# ============================================================
# AGENT 1 — FormGeneratorAgent
# ============================================================

QuestionType = Literal[
    "short_answer",
    "paragraph",
    "multiple_choice",
    "checkboxes",
    "linear_scale",
]

DifficultyLevel = Literal["facile", "moyen", "difficile"]


class ScaleConfig(BaseModel):
    """Configuration pour les questions de type linear_scale."""
    min: int = Field(1, ge=1, le=10)
    max: int = Field(5, ge=1, le=10)
    min_label: str | None = None
    max_label: str | None = None


class FormQuestion(BaseModel):
    """Une question dans un formulaire Google Forms."""
    id: str = Field(..., description="Identifiant unique (ins_01, av_01, etc.)")
    type: QuestionType
    label: str
    required: bool = True
    options: list[str] | None = None
    scale: ScaleConfig | None = None
    # Champs spécifiques aux tests (AVANT / APRÈS)
    correct_answer: str | None = None
    score: int | None = None
    difficulty: DifficultyLevel | None = None
    concept: str | None = None


class FormSection(BaseModel):
    """Une section du formulaire (inscription, test_avant, etc.)."""
    title: str
    description: str | None = None
    duration_minutes: int | None = None
    questions: list[FormQuestion]


class FormGenerationMetadata(BaseModel):
    """Métadonnées de la génération."""
    domaine: str
    niveau_cible: str
    nombre_questions_test: int
    duree_estimee_test_minutes: int
    langue: str = "fr"


class FormGenerationResponse(BaseModel):
    """
    Réponse complète de l'Agent 1 (FormGeneratorAgent).

    Contient les 4 formulaires à créer via Google Forms API :
    - inscription
    - test_avant
    - test_apres
    - satisfaction
    """
    inscription: FormSection
    test_avant: FormSection
    test_apres: FormSection
    satisfaction: FormSection
    metadata: FormGenerationMetadata

    class Config:
        json_schema_extra = {
            "example": {
                "inscription": {
                    "title": "Inscription — Introduction à l'IA",
                    "description": "Formulaire d'inscription",
                    "questions": [
                        {
                            "id": "ins_01",
                            "type": "short_answer",
                            "label": "Nom complet",
                            "required": True,
                        }
                    ],
                },
                "test_avant": {
                    "title": "Test AVANT — Introduction à l'IA",
                    "duration_minutes": 20,
                    "questions": [
                        {
                            "id": "av_01",
                            "type": "multiple_choice",
                            "label": "Que signifie IA ?",
                            "options": ["A. ...", "B. ..."],
                            "correct_answer": "A",
                            "score": 1,
                            "difficulty": "facile",
                            "concept": "Définition",
                        }
                    ],
                },
                "test_apres": {
                    "title": "Test APRÈS — Introduction à l'IA",
                    "duration_minutes": 20,
                    "questions": [],
                },
                "satisfaction": {
                    "title": "Enquête de satisfaction",
                    "questions": [],
                },
                "metadata": {
                    "domaine": "IA",
                    "niveau_cible": "Intermédiaire",
                    "nombre_questions_test": 12,
                    "duree_estimee_test_minutes": 20,
                    "langue": "fr",
                },
            }
        }

# ============================================================
# AGENT 2 — LevelAnalyzerAgent
# ============================================================

class LevelDistribution(BaseModel):
    """Distribution d'un niveau (nb + pourcentage)."""
    nb: int = Field(..., ge=0)
    pourcentage: str


class LevelDistributionSet(BaseModel):
    """Distribution complète des niveaux (3 catégories)."""
    debutants: LevelDistribution
    intermediaires: LevelDistribution
    avances: LevelDistribution


class LevelStatistics(BaseModel):
    """Statistiques globales de progression."""
    score_moyen_avant: float = Field(..., ge=0, le=100)
    score_moyen_apres: float = Field(..., ge=0, le=100)
    progression_absolue: float
    progression_relative: str
    nb_participants: int = Field(..., ge=0)


class NoteworthyCase(BaseModel):
    """Cas remarquable (meilleure progression / à risque)."""
    nom: str
    avant: float
    apres: float
    gain: float


class LevelNoteworthyCases(BaseModel):
    """Cas remarquables."""
    meilleure_progression: NoteworthyCase | None = None
    progressions_faibles: list[NoteworthyCase] = []


class LevelAnalysisMetadata(BaseModel):
    """Métadonnées de l'analyse."""
    source: Literal["llm", "fallback_template"]
    generated_at: str
    duration_seconds: float
    session_id: int | None = None


class LevelAnalysisResponse(BaseModel):
    """
    Réponse complète de l'Agent 2 (LevelAnalyzerAgent).

    Contient l'analyse des niveaux et la progression.
    """
    success: bool = True
    resume: str
    statistiques: LevelStatistics
    distribution_avant: LevelDistributionSet
    distribution_apres: LevelDistributionSet
    cas_remarquables: LevelNoteworthyCases
    recommandations: list[str] = Field(..., min_length=3, max_length=5)
    interpretation: str
    metadata: LevelAnalysisMetadata  

# ============================================================
# AGENT 3 — SatisfactionAnalyzerAgent
# ============================================================

class SatisfactionNotes(BaseModel):
    """Notes moyennes de satisfaction (1-5)."""
    note_globale: float = Field(..., ge=0, le=5)
    note_formateur: float = Field(..., ge=0, le=5)
    note_contenu: float = Field(..., ge=0, le=5)
    note_supports: float = Field(..., ge=0, le=5)
    note_organisation: float = Field(..., ge=0, le=5)


class SatisfactionStats(BaseModel):
    """Statistiques déterministes calculées par pandas."""
    notes: SatisfactionNotes
    taux_recommandation: str
    nb_reponses: int = Field(..., ge=0)
    nb_recommandent: int = Field(0, ge=0)
    nb_neutres: int = Field(0, ge=0)
    nb_deconseillent: int = Field(0, ge=0)


class SatisfactionTheme(BaseModel):
    """Thème récurrent identifié dans les feedbacks."""
    theme: str
    frequence: Literal["faible", "moyenne", "élevée"]
    sentiment: Literal["positif", "négatif", "neutre"]


class SatisfactionAnalysisMetadata(BaseModel):
    """Métadonnées de l'analyse."""
    source: Literal["llm", "fallback_template"]
    generated_at: str
    duration_seconds: float
    session_id: int | None = None


class SatisfactionAnalysisResponse(BaseModel):
    """
    Réponse complète de l'Agent 3 (SatisfactionAnalyzerAgent).
    """
    success: bool = True
    resume: str
    statistiques: SatisfactionStats
    points_forts: list[str] = Field(..., min_length=1, max_length=3)
    axes_amelioration: list[str] = Field(..., min_length=1, max_length=3)
    themes_recurrents: list[SatisfactionTheme] = []
    recommandations: list[str] = Field(..., min_length=3, max_length=5)
    interpretation: str
    metadata: SatisfactionAnalysisMetadata      


# ============================================================
# AGENT 4 — PresenceAnalyzerAgent 
# ============================================================

class PresenceStatistics(BaseModel):
    """Statistiques globales de présence."""
    total_participants: int = Field(..., ge=0)
    total_seances: int = Field(..., ge=0)
    taux_presence_global: str
    nb_presents_moyen: float = Field(..., ge=0)
    nb_absents_total: int = Field(..., ge=0)


class ParticipantPresence(BaseModel):
    """Résumé de présence d'un participant."""
    participant_id: int | None = None
    nom: str
    nb_presences: int = Field(..., ge=0)
    nb_seances: int = Field(..., ge=0)
    taux_presence: str
    eligible_attestation: bool = Field(
        ...,
        description="True si taux_presence ≥ 80%",
    )


class PresenceAnomalyType(str):
    """Types d'anomalies détectables."""
    # Utilisé comme Literal dans PresenceAnomaly


class PresenceAnomaly(BaseModel):
    """Anomalie détectée dans les présences."""
    type: Literal[
        "doublon",
        "absence_incoherente",
        "participant_inconnu",
        "hors_plage",
        "presence_manquante",
    ]
    severity: Literal["info", "warning", "error"]
    message: str
    participant_nom: str | None = None
    participant_id: int | None = None
    details: dict[str, Any] | None = None


class PresenceAnalysisMetadata(BaseModel):
    """Métadonnées de l'analyse."""
    generated_at: str
    duration_seconds: float
    session_id: int | None = None
    methode: str = "python_deterministic"


class PresenceAnalysisResponse(BaseModel):
    """
    Réponse complète de l'Agent 4 (PresenceAnalyzerAgent).

    ⚠️ Analyse 100% Python — aucun LLM utilisé.
    """
    success: bool = True
    resume: str
    statistiques: PresenceStatistics
    participants: list[ParticipantPresence] = []
    anomalies: list[PresenceAnomaly] = []
    eligibles_attestation: list[str] = Field(
        default_factory=list,
        description="Noms des participants éligibles (≥ 80%)",
    )
    non_eligibles_attestation: list[str] = Field(
        default_factory=list,
        description="Noms des participants non éligibles (< 80%)",
    )
    recommandations: list[str] = []
    metadata: PresenceAnalysisMetadata

# ============================================================
# AGENT 5 — AttestationGeneratorAgent
# ============================================================

class AttestationDetails(BaseModel):
    """Détails de la formation dans l'attestation."""
    formation: str
    dates: str
    lieu: str
    duree: str
    formateur: str
    domaine: str
    niveau: str


class AttestationContent(BaseModel):
    """Contenu texte d'une attestation (avant génération PDF)."""
    titre_attestation: str = "ATTESTATION DE FORMATION"
    introduction: str
    corps: str
    details: AttestationDetails
    competences: list[str] = Field(..., min_length=3, max_length=5)
    cloture: str = (
        "En foi de quoi, la présente attestation lui est délivrée "
        "pour servir et valoir ce que de droit."
    )
    lieu_emission: str = "Antananarivo"
    date_emission: str


class AttestationGenerationMetadata(BaseModel):
    """Métadonnées de la génération (utile pour debug / traçabilité)."""
    source: Literal["llm", "fallback_template"] = Field(
        ...,
        description="Source du contenu : LLM (Groq) ou template Python (fallback)",
    )
    generated_at: str
    duration_seconds: float
    participant_id: int | None = None
    session_id: int | None = None


class AttestationGenerationResponse(BaseModel):
    """
    Réponse complète de l'Agent 5 pour UN participant.

    Utilisé par le Backend (attestation_service.py) pour générer le PDF.
    """
    success: bool = True
    participant: dict[str, Any]
    content: AttestationContent
    numero_unique: str = Field(
        ...,
        description="Numéro unique d'attestation (ex: ALT-2026-IA-0001)",
    )
    metadata: AttestationGenerationMetadata


class BatchAttestationResponse(BaseModel):
    """Réponse batch — pour tous les participants éligibles."""
    success: bool = True
    session_id: int | None = None
    total_eligible: int
    total_generated: int
    total_failed: int = 0
    attestations: list[AttestationGenerationResponse]
    failed_participants: list[dict[str, Any]] = []
    duration_seconds: float
    
# ============================================================
# AGENT 6 — ReportGeneratorAgent
# ============================================================

class ReportPresentation(BaseModel):
    """Section présentation de la formation."""
    titre_formation: str
    dates: str
    lieu: str
    duree: str
    formateur: str
    public_cible: str
    nombre_participants: int


class ReportStatsParticipants(BaseModel):
    """Section statistiques participants."""
    total_inscrits: int
    total_presents: int
    taux_presence_moyen: str
    entreprises: list[str] = []
    commentaire: str = ""


class ReportNiveauDistribution(BaseModel):
    """Distribution des niveaux (avant ou après)."""
    debutants: str
    intermediaires: str
    avances: str


class ReportAnalyseNiveaux(BaseModel):
    """Section analyse des niveaux avant/après."""
    avant: ReportNiveauDistribution
    apres: ReportNiveauDistribution
    progression_globale: str
    commentaire: str = ""


class ReportSatisfaction(BaseModel):
    """Section satisfaction."""
    note_globale: str
    note_formateur: str
    note_contenu: str
    note_supports: str
    note_organisation: str
    points_forts: list[str] = []
    axes_amelioration: list[str] = []
    taux_recommandation: str = ""


class ReportGenerationMetadata(BaseModel):
    """Métadonnées de la génération du rapport."""
    source: Literal["llm", "fallback_template"]
    generated_at: str
    duration_seconds: float
    session_id: int | None = None


class ReportGenerationResponse(BaseModel):
    """
    Réponse complète de l'Agent 6 (ReportGeneratorAgent).

    Contient le rapport final structuré en JSON.
    La génération Word/PDF est déléguée au Backend.
    """
    success: bool = True
    titre_rapport: str
    resume_executif: str
    presentation: ReportPresentation
    statistiques_participants: ReportStatsParticipants
    analyse_niveaux: ReportAnalyseNiveaux
    satisfaction: ReportSatisfaction
    recommandations: list[str] = Field(..., min_length=3, max_length=5)
    conclusion: str
    lieu_emission: str 
    date_emission: str
    metadata: ReportGenerationMetadata