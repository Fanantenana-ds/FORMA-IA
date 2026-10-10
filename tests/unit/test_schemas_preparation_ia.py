# ============================================================
# TESTS — app/schemas/preparation_ia.py (EDT + Budget)
# ============================================================
# Schémas Pydantic uniquement : aucun LLM, aucune base, aucun réseau.
# ============================================================

import pytest
from pydantic import ValidationError

from app.schemas.preparation_ia import (
    EDTSession,
    EDTPause,
    EDTJour,
    EDTFormateur,
    EDTSalle,
    EDTResume,
    EDTResponse,
    CoutDetail,
    BudgetPrevisionnel,
    PreparationCompleteData,
    PreparationCompleteResponse,
    CalculateBudgetRequest,
    GenerateEDTRequest,
    GeneratePreparationCompleteRequest,
    RegeneratePreparationRequest,
)


def test_edt_response_valide():
    jour = EDTJour(
        numero=1, date="2026-10-15", jour_semaine="Jeudi",
        sessions=[
            EDTSession(
                id="s_01_01", heure_debut="08:00", heure_fin="10:00",
                module="Introduction", type="cours", duree_minutes=120,
                formateur="M. RANAIVOSOA", salle="Salle A", objectifs=["Comprendre les bases"],
            ),
        ],
        pauses=[EDTPause(heure_debut="10:00", heure_fin="10:15")],
    )
    reponse = EDTResponse(
        titre_formation="Introduction à l'IA",
        duree_totale_jours=2,
        nombre_modules=4,
        formateur=EDTFormateur(nom="M. RANAIVOSOA", specialite="IA"),
        salle=EDTSalle(nom="Salle A", adresse="Antananarivo"),
        jours=[jour],
        resume_hebdomadaire=EDTResume(
            total_heures=14.0, total_sessions=8, modules_couverts=4, charge_journaliere_moyenne=7.0,
        ),
    )
    assert reponse.jours[0].sessions[0].type == "cours"
    assert reponse.resume_hebdomadaire.total_heures == 14.0


def test_edt_session_type_invalide_refuse():
    with pytest.raises(ValidationError):
        EDTSession(
            id="x", heure_debut="08:00", heure_fin="10:00",
            module="x", type="type_inexistant", duree_minutes=60,
        )


def test_edt_session_duree_negative_refusee():
    with pytest.raises(ValidationError):
        EDTSession(
            id="x", heure_debut="08:00", heure_fin="10:00",
            module="x", type="cours", duree_minutes=-30,  # ge=0
        )


def test_budget_previsionnel_valide():
    budget = BudgetPrevisionnel(
        cout_formateur=1000000, cout_salle=400000, cout_supports=100000,
        cout_total=1500000,
        details=[CoutDetail(libelle="Formateur", base=500000, quantite=2, montant=1000000)],
    )
    assert budget.devise == "MGA"
    assert budget.details[0].montant == 1000000


def test_budget_previsionnel_montant_negatif_refuse():
    with pytest.raises(ValidationError):
        BudgetPrevisionnel(
            cout_formateur=-1, cout_salle=0, cout_supports=0, cout_total=0,  # ge=0
        )


def test_preparation_complete_response_valide():
    edt = EDTResponse(titre_formation="x", duree_totale_jours=2, nombre_modules=1)
    budget = BudgetPrevisionnel(cout_formateur=1000000, cout_salle=0, cout_supports=0, cout_total=1000000)
    data = PreparationCompleteData(budget=budget, edt=edt)
    assert data.budget.cout_total == 1000000

    reponse = PreparationCompleteResponse(
        projet_id=1, budget=budget, edt=edt,
        _review_id="HITL-PREP-0001", _review_status="pending_review",
    )
    assert reponse.review_id == "HITL-PREP-0001"


# ---- Schémas de requête ----

def test_calculate_budget_request_valide():
    req = CalculateBudgetRequest(
        formateur_info={"nom": "M. RANAIVOSOA", "tarif_journalier": 500000},
        salle_info={"nom": "Salle A", "tarif_journalier": 200000},
        nb_jours=2, nb_participants=20,
    )
    assert req.nb_jours == 2


def test_calculate_budget_request_nb_jours_hors_bornes_refuse():
    with pytest.raises(ValidationError):
        CalculateBudgetRequest(
            formateur_info={}, salle_info={}, nb_jours=31, nb_participants=20,  # > le=30
        )


def test_generate_edt_request_valide():
    req = GenerateEDTRequest(
        titre_formation="Introduction à l'IA",
        modules=[{"titre": "Introduction", "duree": "3h"}],
        dates=["2026-10-15", "2026-10-16"],
    )
    assert len(req.dates) == 2


def test_generate_edt_request_titre_trop_court_refuse():
    with pytest.raises(ValidationError):
        GenerateEDTRequest(titre_formation="IA", modules=[], dates=[])  # min_length=3


def test_generate_preparation_complete_request_valide():
    req = GeneratePreparationCompleteRequest(
        offre_data={"reference": "x"}, projet_info={"client": "x"}, ressources={"formateur": {}},
    )
    assert req.options == {}


def test_regenerate_preparation_request_feedback_trop_court_refuse():
    with pytest.raises(ValidationError):
        RegeneratePreparationRequest(review_id="HITL-1", feedback="court")  # < min_length=10
