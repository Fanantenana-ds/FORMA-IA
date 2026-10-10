# ============================================================
# TESTS — app/schemas/offre_ia.py (M3, offres technique/financière)
# ============================================================
# Schémas Pydantic uniquement : aucun LLM, aucune base, aucun réseau.
# ============================================================

import pytest
from pydantic import ValidationError

from app.schemas.offre_ia import (
    PresentationStructure,
    ComprehensionBesoin,
    ApprocheMethodologique,
    ArchitectureStack,
    ArchitectureComposant,
    ArchitectureTechnique,
    ProgrammeModule,
    Programme,
    RessourcesFormateur,
    Ressources,
    PlanningJalon,
    Planning,
    Garanties,
    Annexes,
    OffreTechniqueResponse,
    DetailCout,
    Remise,
    TVA,
    Recapitulatif,
    Echeance,
    ConditionsFinancieres,
    OffreFinanciereResponse,
    OffreCompleteResponse,
    GenerateOffreTechniqueRequest,
    GenerateOffreFinanciereRequest,
    GenerateOffreCompleteRequest,
    RegenerateOffreRequest,
)


def test_offre_technique_response_valide():
    reponse = OffreTechniqueResponse(
        titre_offre="Formation Introduction à l'IA",
        reference="ALT-OFF-TECH-2026-0001",
        date_emission="2026-09-24",
        presentation_structure=PresentationStructure(
            description="ALTIORA Prest est un cabinet de formation.",
            domaines_expertise=["IA", "Data"],
        ),
        comprehension_besoin=ComprehensionBesoin(public_cible="Agents de santé"),
        approche_methodologique=ApprocheMethodologique(
            pedagogie="Active", modalites="Présentiel",
        ),
        architecture_technique=ArchitectureTechnique(
            stack=ArchitectureStack(frontend="React", backend="FastAPI"),
            composants=[ArchitectureComposant(nom="API", role="Backend")],
        ),
        programme=Programme(
            duree_totale="2 jours",
            modules=[ProgrammeModule(numero=1, titre="Introduction", duree="3h", methode="Cours")],
        ),
        ressources=Ressources(
            formateur=RessourcesFormateur(nom="M. RANAIVOSOA", profil="Expert IA"),
        ),
        planning=Planning(
            jalons=[PlanningJalon(date="2026-10-15", livrable="Kickoff")],
        ),
        garanties=Garanties(qualite="Satisfait ou recommencé"),
        annexes=Annexes(references=["Formation X 2025"]),
        conclusion="Une offre adaptée à vos besoins.",
    )
    assert reponse.success is True
    assert reponse.programme.modules[0].numero == 1
    assert reponse.architecture_technique.stack.backend == "FastAPI"


def test_programme_module_numero_doit_etre_positif():
    with pytest.raises(ValidationError):
        ProgrammeModule(numero=0, titre="x", duree="1h", methode="x")  # ge=1


def test_offre_financiere_response_valide():
    reponse = OffreFinanciereResponse(
        titre_offre="Formation Introduction à l'IA",
        reference="ALT-OFF-FIN-2026-0001",
        date_emission="2026-09-24",
        details_couts={
            "formateur": DetailCout(tarif_journalier=500000, nb_jours=2, montant=1000000),
        },
        recapitulatif=Recapitulatif(
            sous_total_ht=1000000,
            tva=TVA(montant=200000),
            total_ttc=1200000,
            remises=[Remise(type="quantitative", description="10 pers.+", pourcentage=5.0, montant=50000)],
            net_a_payer=1150000,
        ),
        echeancier=[
            Echeance(ordre=1, libelle="À la signature", pourcentage=50.0, montant=575000, delai="Immédiat"),
        ],
        conditions_financieres=ConditionsFinancieres(
            validite_offre="60 jours", modalites_paiement="Virement bancaire",
        ),
        conclusion="Tarif compétitif.",
    )
    assert reponse.recapitulatif.tva.taux == 20.0
    assert reponse.conditions_financieres.monnaie == "MGA"


def test_remise_pourcentage_hors_bornes_refuse():
    with pytest.raises(ValidationError):
        Remise(type="x", description="x", pourcentage=150.0, montant=1000)  # > le=100


def test_offre_complete_response_valide():
    reponse = OffreCompleteResponse(
        offre_technique={"titre_offre": "x"},
        offre_financiere={"titre_offre": "x"},
        _review_id="HITL-M3-0001",
        _review_status="pending_review",
        docx_path="offre.docx",
    )
    assert reponse.review_id == "HITL-M3-0001"


# ---- Schémas de requête ----

def test_generate_offre_technique_request_valide():
    req = GenerateOffreTechniqueRequest(
        tdr_data={"client": "Ministère"}, session_info={"nb_participants": 20},
    )
    assert req.tdr_data["client"] == "Ministère"


def test_generate_offre_financiere_request_valide():
    req = GenerateOffreFinanciereRequest(
        tdr_data={"client": "x"}, session_info={"nb_participants": 20},
        options={"tva_applicable": True},
    )
    assert req.options["tva_applicable"] is True


def test_generate_offre_complete_request_valide():
    req = GenerateOffreCompleteRequest(tdr_data={"client": "x"}, session_info={})
    assert req.options == {}


def test_regenerate_offre_request_feedback_trop_court_refuse():
    with pytest.raises(ValidationError):
        RegenerateOffreRequest(review_id="HITL-1", feedback="court")  # < min_length=10


def test_regenerate_offre_request_valide():
    req = RegenerateOffreRequest(review_id="HITL-1", feedback="Merci de revoir le budget total.")
    assert req.review_id == "HITL-1"
