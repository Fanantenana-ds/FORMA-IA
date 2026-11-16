from app.services.offres.offre_technique_service import OffreTechniqueGeneratorService
from app.services.offres.offre_financiere_service import OffreFinanciereGeneratorService
from app.services.offres.offre_financiere_service import OffreFinanciereGeneratorService


def test_offre_reprend_les_faits_du_tdr_et_ne_confond_pas_titre_et_client():
    service = OffreTechniqueGeneratorService()
    generated = {
        "titre_offre": "titre halluciné",
        "presentation_structure": {"nom": "Autre société", "description": "inventé"},
        "comprehension_besoin": {
            "objectifs_client": ["objectif halluciné"],
            "public_cible": "FID",
        },
        "architecture_technique": {"stack": {"backend": "Node.js"}},
        "programme": {
            "duree_totale": "2 jours (14 heures)",
            "modules": [
                {"titre": "Module 1", "duree": "3h"},
                {"titre": "Module 2", "duree": "3h"},
            ],
        },
        "ressources": {"formateur": {"nom": "Nom inventé", "profil": "10 ans"}},
        "planning": {"dates_proposees": ["2026-12-01"], "jalons": []},
        "garanties": {"qualite": "Satisfaction garantie à 100%", "suivi": "1 mois"},
        "annexes": {"references": ["Client XYZ"]},
    }

    result = service._apply_source_constraints(
        generated,
        {
            "titre": "Formation IA appliquée",
            "objectifs": ["Analyser des données avec des outils IA"],
            "public_cible": "Équipe technique",
            "duree_totale": "2 jours (14 heures)",
            "formateur_profil": "Expérience en IA appliquée",
        },
        {
            "titre": "Formation IA appliquée",
            "client": "Formation IA appliquée",
            "references_portfolio": ["extrait non qualifié"],
        },
    )

    assert result["titre_offre"] == "Offre technique — Formation IA appliquée"
    assert result["client"] == "À confirmer avec le client"
    assert result["presentation_structure"]["nom"] == "ALTIORA PREST"
    assert result["comprehension_besoin"]["objectifs_client"] == [
        "Analyser des données avec des outils IA"
    ]
    assert result["architecture_technique"] is None
    assert result["programme"]["duree_totale"] == "2 jours (14 heures)"
    assert all("À répartir" in module["duree"] for module in result["programme"]["modules"])
    assert "alerte_coherence_duree" in result["programme"]
    assert result["ressources"]["formateur"]["nom"] == "Formateur à mobiliser après attribution"
    assert result["ressources"]["formateur"]["profil"] == "Expérience en IA appliquée"
    assert result["planning"]["dates_proposees"] == []
    assert result["garanties"]["suivi"] is None
    assert result["annexes"]["references"] == []


def test_formateur_interne_n_est_nomme_que_si_affectation_explicitement_confirmee():
    service = OffreTechniqueGeneratorService()
    result = service._apply_source_constraints(
        {"ressources": {"formateur": {"profil": "Formateur IA"}}},
        {},
        {"formateur_confirme": "M. Sanda", "formateur_interne_confirme": True},
    )

    trainer = result["ressources"]["formateur"]
    assert trainer["nom"] == "M. Sanda"
    assert trainer["mode_mobilisation"] == "Interne — affectation confirmée"


def test_portfolio_textuel_non_structure_ne_casse_pas_le_prompt():
    service = OffreTechniqueGeneratorService()
    prompt = service._build_user_prompt(
        {"titre": "Formation IA"},
        {"references_portfolio": ["extrait de support", {"intitule": "Parcours IA", "annee": "2025"}]},
    )

    assert "Parcours IA" in prompt
    assert "- extrait de support (" not in prompt




def test_fallback_financier_ne_fabrique_pas_les_conditions_contractuelles():
    service = OffreFinanciereGeneratorService()
    result = service._generate_with_template(
        {"titre_offre": "Offre technique — Formation IA"},
        {},
        {
            "details_couts": {},
            "recapitulatif": {},
        },
        [],
    )

    conditions = result["conditions_financieres"]
    assert conditions["validite_offre"] == "À confirmer avant transmission au client"
    assert conditions["modalites_paiement"] == "À convenir avec le client"
    assert conditions["penalites_retard"] is None
    assert "validation humaine" in result["notes"][0]
