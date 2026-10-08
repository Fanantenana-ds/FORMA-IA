# ============================================================
# TESTS — app/schemas/formation_ia.py (M5, 6 agents)
# ============================================================
# Schémas Pydantic uniquement : aucun LLM, aucune base, aucun réseau.
# Objectif : couvrir les schémas jamais importés par la suite existante
# (0 % avant ce fichier), sans toucher au code de production.
# ============================================================

import pytest
from pydantic import ValidationError

from app.schemas.formation_ia import (
    ScaleConfig,
    FormQuestion,
    FormSection,
    FormGenerationMetadata,
    FormGenerationResponse,
    LevelDistribution,
    LevelDistributionSet,
    LevelStatistics,
    NoteworthyCase,
    LevelNoteworthyCases,
    LevelAnalysisMetadata,
    LevelAnalysisResponse,
    SatisfactionNotes,
    SatisfactionStats,
    SatisfactionTheme,
    SatisfactionAnalysisMetadata,
    SatisfactionAnalysisResponse,
    PresenceStatistics,
    ParticipantPresence,
    PresenceAnomaly,
    PresenceAnalysisMetadata,
    PresenceAnalysisResponse,
    AttestationDetails,
    AttestationContent,
    AttestationGenerationMetadata,
    AttestationGenerationResponse,
    BatchAttestationResponse,
    ReportPresentation,
    ReportStatsParticipants,
    ReportNiveauDistribution,
    ReportAnalyseNiveaux,
    ReportSatisfaction,
    ReportGenerationMetadata,
    ReportGenerationResponse,
)


# ---- Agent 1 — FormGeneratorAgent ----

def test_form_generation_response_valide():
    section = FormSection(
        title="Inscription",
        questions=[
            FormQuestion(id="ins_01", type="short_answer", label="Nom complet"),
            FormQuestion(
                id="av_01", type="linear_scale", label="Niveau",
                scale=ScaleConfig(min=1, max=5, min_label="Débutant", max_label="Expert"),
                difficulty="facile", concept="Auto-évaluation",
            ),
        ],
    )
    reponse = FormGenerationResponse(
        inscription=section,
        test_avant=section,
        test_apres=section,
        satisfaction=section,
        metadata=FormGenerationMetadata(
            domaine="IA", niveau_cible="Intermédiaire",
            nombre_questions_test=12, duree_estimee_test_minutes=20,
        ),
    )
    assert reponse.metadata.langue == "fr"
    assert len(reponse.inscription.questions) == 2


def test_form_question_type_invalide_refuse():
    with pytest.raises(ValidationError):
        FormQuestion(id="x", type="type_inexistant", label="Question")


# ---- Agent 2 — LevelAnalyzerAgent ----

def _distribution(nb=5, pct="50.0%"):
    return LevelDistribution(nb=nb, pourcentage=pct)


def test_level_analysis_response_valide():
    reponse = LevelAnalysisResponse(
        resume="Progression significative.",
        statistiques=LevelStatistics(
            score_moyen_avant=40.0, score_moyen_apres=65.0,
            progression_absolue=25.0, progression_relative="62.5%", nb_participants=10,
        ),
        distribution_avant=LevelDistributionSet(
            debutants=_distribution(6, "60.0%"), intermediaires=_distribution(3, "30.0%"),
            avances=_distribution(1, "10.0%"),
        ),
        distribution_apres=LevelDistributionSet(
            debutants=_distribution(2, "20.0%"), intermediaires=_distribution(5, "50.0%"),
            avances=_distribution(3, "30.0%"),
        ),
        cas_remarquables=LevelNoteworthyCases(
            meilleure_progression=NoteworthyCase(nom="A", avant=30.0, apres=90.0, gain=60.0),
            progressions_faibles=[NoteworthyCase(nom="B", avant=20.0, apres=25.0, gain=5.0)],
        ),
        recommandations=["Reco 1", "Reco 2", "Reco 3"],
        interpretation="Le groupe a bien progressé.",
        metadata=LevelAnalysisMetadata(source="llm", generated_at="2026-09-24T10:00:00", duration_seconds=1.2),
    )
    assert reponse.success is True
    assert reponse.statistiques.score_moyen_apres == 65.0


def test_level_analysis_response_recommandations_min_3_refuse():
    with pytest.raises(ValidationError):
        LevelAnalysisResponse(
            resume="x",
            statistiques=LevelStatistics(
                score_moyen_avant=40.0, score_moyen_apres=65.0,
                progression_absolue=25.0, progression_relative="62.5%", nb_participants=10,
            ),
            distribution_avant=LevelDistributionSet(
                debutants=_distribution(), intermediaires=_distribution(), avances=_distribution(),
            ),
            distribution_apres=LevelDistributionSet(
                debutants=_distribution(), intermediaires=_distribution(), avances=_distribution(),
            ),
            cas_remarquables=LevelNoteworthyCases(),
            recommandations=["Une seule reco"],  # < min_length=3
            interpretation="x",
            metadata=LevelAnalysisMetadata(source="llm", generated_at="x", duration_seconds=1.0),
        )


def test_level_statistics_score_hors_bornes_refuse():
    with pytest.raises(ValidationError):
        LevelStatistics(
            score_moyen_avant=150.0,  # > le=100
            score_moyen_apres=65.0, progression_absolue=25.0,
            progression_relative="x", nb_participants=10,
        )


# ---- Agent 3 — SatisfactionAnalyzerAgent ----

def test_satisfaction_analysis_response_valide():
    reponse = SatisfactionAnalysisResponse(
        resume="Bonne satisfaction générale.",
        statistiques=SatisfactionStats(
            notes=SatisfactionNotes(
                note_globale=4.2, note_formateur=4.5, note_contenu=4.0,
                note_supports=3.8, note_organisation=4.1,
            ),
            taux_recommandation="90%", nb_reponses=10, nb_recommandent=9,
            nb_neutres=1, nb_deconseillent=0,
        ),
        points_forts=["Formateur compétent"],
        axes_amelioration=["Supports à enrichir"],
        themes_recurrents=[SatisfactionTheme(theme="Pédagogie", frequence="élevée", sentiment="positif")],
        recommandations=["Reco 1", "Reco 2", "Reco 3"],
        interpretation="Satisfaction élevée.",
        metadata=SatisfactionAnalysisMetadata(source="fallback_template", generated_at="x", duration_seconds=0.5),
    )
    assert reponse.statistiques.notes.note_globale == 4.2
    assert reponse.themes_recurrents[0].sentiment == "positif"


def test_satisfaction_note_hors_bornes_refuse():
    with pytest.raises(ValidationError):
        SatisfactionNotes(
            note_globale=6.0,  # > le=5
            note_formateur=4.0, note_contenu=4.0, note_supports=4.0, note_organisation=4.0,
        )


# ---- Agent 4 — PresenceAnalyzerAgent ----

def test_presence_analysis_response_valide():
    reponse = PresenceAnalysisResponse(
        resume="2 anomalies détectées.",
        statistiques=PresenceStatistics(
            total_participants=10, total_seances=4, taux_presence_global="85%",
            nb_presents_moyen=8.5, nb_absents_total=6,
        ),
        participants=[
            ParticipantPresence(nom="A", nb_presences=4, nb_seances=4, taux_presence="100%", eligible_attestation=True),
            ParticipantPresence(nom="B", nb_presences=2, nb_seances=4, taux_presence="50%", eligible_attestation=False),
        ],
        anomalies=[
            PresenceAnomaly(type="doublon", severity="warning", message="Doublon détecté", participant_nom="A"),
        ],
        eligibles_attestation=["A"],
        non_eligibles_attestation=["B"],
        metadata=PresenceAnalysisMetadata(generated_at="x", duration_seconds=0.1),
    )
    assert reponse.metadata.methode == "python_deterministic"
    assert reponse.anomalies[0].type == "doublon"


def test_presence_anomaly_type_invalide_refuse():
    with pytest.raises(ValidationError):
        PresenceAnomaly(type="type_inconnu", severity="warning", message="x")


# ---- Agent 5 — AttestationGeneratorAgent ----

def _attestation_content():
    return AttestationContent(
        introduction="Introduction.",
        corps="Corps de l'attestation.",
        details=AttestationDetails(
            formation="Introduction à l'IA", dates="15-16/10/2026", lieu="Antananarivo",
            duree="2 jours", formateur="M. RANAIVOSOA", domaine="IA", niveau="Intermédiaire",
        ),
        competences=["Comp 1", "Comp 2", "Comp 3"],
        date_emission="2026-10-17",
    )


def test_attestation_generation_response_valide():
    reponse = AttestationGenerationResponse(
        participant={"nom": "A", "id": 1},
        content=_attestation_content(),
        numero_unique="ALT-2026-IA-0001",
        metadata=AttestationGenerationMetadata(source="llm", generated_at="x", duration_seconds=0.8),
    )
    assert reponse.numero_unique.startswith("ALT-2026")


def test_batch_attestation_response_valide():
    attestation = AttestationGenerationResponse(
        participant={"nom": "A"}, content=_attestation_content(),
        numero_unique="ALT-2026-IA-0001",
        metadata=AttestationGenerationMetadata(source="llm", generated_at="x", duration_seconds=0.8),
    )
    batch = BatchAttestationResponse(
        total_eligible=1, total_generated=1, attestations=[attestation], duration_seconds=1.0,
    )
    assert batch.total_failed == 0
    assert len(batch.attestations) == 1


def test_attestation_content_competences_min_3_refuse():
    with pytest.raises(ValidationError):
        AttestationContent(
            introduction="x", corps="x",
            details=AttestationDetails(
                formation="x", dates="x", lieu="x", duree="x", formateur="x", domaine="x", niveau="x",
            ),
            competences=["Une seule"],  # < min_length=3
            date_emission="x",
        )


# ---- Agent 6 — ReportGeneratorAgent ----

def test_report_generation_response_valide():
    reponse = ReportGenerationResponse(
        titre_rapport="Rapport — Introduction à l'IA",
        resume_executif="Formation réussie.",
        presentation=ReportPresentation(
            titre_formation="Introduction à l'IA", dates="15-16/10/2026", lieu="Antananarivo",
            duree="2 jours", formateur="M. RANAIVOSOA", public_cible="Agents", nombre_participants=10,
        ),
        statistiques_participants=ReportStatsParticipants(
            total_inscrits=10, total_presents=9, taux_presence_moyen="90%",
        ),
        analyse_niveaux=ReportAnalyseNiveaux(
            avant=ReportNiveauDistribution(debutants="60%", intermediaires="30%", avances="10%"),
            apres=ReportNiveauDistribution(debutants="20%", intermediaires="50%", avances="30%"),
            progression_globale="+25 points",
        ),
        satisfaction=ReportSatisfaction(
            note_globale="4.2/5", note_formateur="4.5/5", note_contenu="4.0/5",
            note_supports="3.8/5", note_organisation="4.1/5",
        ),
        recommandations=["Reco 1", "Reco 2", "Reco 3"],
        conclusion="Formation à reconduire.",
        lieu_emission="Antananarivo",
        date_emission="2026-10-17",
        metadata=ReportGenerationMetadata(source="llm", generated_at="x", duration_seconds=2.0),
    )
    assert reponse.presentation.nombre_participants == 10
    assert reponse.analyse_niveaux.apres.avances == "30%"
