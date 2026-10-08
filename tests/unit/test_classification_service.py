"""
Tests de ClassificationService (M1) — correction du faux positif par
sous-chaîne : un mot-clé court ("ia", "bi"...) matché par simple "in" faisait
classer en domaine IA/DATA n'importe quel texte contenant ces lettres à
l'intérieur d'un autre mot ("materiaux" contient "ia", "stabilité" contient
"bi"). La correction utilise une frontière de mot (\\b).

Exécution :
    python -m pytest tests/unit/test_classification_service.py -q
"""

import pytest

from app.services.veille.classification_service import ClassificationService


@pytest.fixture
def service():
    return ClassificationService()


def classer(service, titre="", resume=""):
    return service.classify({"title": titre, "summary": resume})


# ============================================================
# Faux positifs corrigés
# ============================================================

@pytest.mark.parametrize("texte", [
    "Information sur la restauration de matériaux de construction",
    "Formation à la gestion des matériaux industriels",
])
def test_materiaux_ne_declenche_plus_le_domaine_ia(service, texte):
    resultat = classer(service, titre=texte)

    assert resultat["domain"] != "ia"
    assert "ia" not in resultat["matched_keywords"]


def test_stabilite_ne_declenche_plus_le_domaine_data(service):
    resultat = classer(service, titre="Amélioration de la stabilité du système")

    assert "bi" not in resultat["matched_keywords"]


def test_redeveloppement_ne_declenche_pas_developpement(service):
    """'redéveloppement' contient 'développement' mais n'est pas ce mot."""
    resultat = classer(service, titre="Projet de redéveloppement urbain")

    assert "développement" not in resultat["matched_keywords"]


# ============================================================
# Vrais positifs toujours détectés (non-régression)
# ============================================================

def test_ia_en_mot_isole_est_toujours_detecte(service):
    resultat = classer(service, titre="Formation IA avancée pour développeurs")

    assert resultat["domain"] == "ia"
    assert "ia" in resultat["matched_keywords"]


def test_intelligence_artificielle_mot_compose_toujours_detecte(service):
    resultat = classer(service, titre="Formation en intelligence artificielle")

    assert resultat["domain"] == "ia"


def test_bi_en_mot_isole_est_toujours_detecte(service):
    resultat = classer(service, titre="Analyse BI et reporting décisionnel")

    assert "bi" in resultat["matched_keywords"]


def test_developpement_normal_est_toujours_detecte(service):
    resultat = classer(service, titre="Poste de développement web")

    assert resultat["domain"] == "developpement"
    assert "développement" in resultat["matched_keywords"]


def test_aucun_mot_cle_donne_le_domaine_autre(service):
    resultat = classer(service, titre="Réunion générale de l'équipe")

    assert resultat["domain"] == "autre"
    assert resultat["matched_keywords"] == []


def test_insensible_a_la_casse(service):
    resultat = classer(service, titre="FORMATION IA")

    assert resultat["domain"] == "ia"


def test_detect_country_inchange():
    """Garde-fou : la correction ne touche que classify(), pas detect_country."""
    domaine = ClassificationService.detect_country(
        {"title": "Poste à Antananarivo", "summary": "", "organizer": ""}
    )
    assert domaine == "Madagascar"


# ============================================================
# Correction 1e — pluriels reconnus (mission "Étape 1")
# ============================================================
# AVANT : \b + mot-clé + \b exigeait une correspondance EXACTE. "bureautique"
# (singulier) ne matchait pas "bureautiques" (pluriel), "application" ne
# matchait pas "applications" -- ces textes, pourtant clairement dans le
# domaine, tombaient dans "autre", ce qui fait baisser la précision de M1.

def test_bureautique_pluriel_est_detecte(service):
    resultat = classer(service, titre="Recherche d'un expert pour nos outils bureautiques")

    assert resultat["domain"] == "bureautique"
    assert "bureautique" in resultat["matched_keywords"]


def test_application_pluriel_est_detecte(service):
    resultat = classer(service, titre="Développement d'applications mobiles pour PME")

    assert resultat["domain"] == "developpement"
    assert "application" in resultat["matched_keywords"]


def test_redeveloppement_pluriel_toujours_refuse(service):
    """Le pluriel ajouté ne doit pas réintroduire le faux positif par
    sous-chaîne déjà corrigé (test_redeveloppement_ne_declenche_pas_developpement)."""
    resultat = classer(service, titre="Projets de redéveloppements urbains")

    assert "développement" not in resultat["matched_keywords"]


def test_materiaux_pluriel_toujours_refuse(service):
    resultat = classer(service, titre="Gestion des matériaux de plusieurs chantiers")

    assert "ia" not in resultat["matched_keywords"]


def test_singulier_toujours_detecte_apres_ajout_du_pluriel(service):
    """Non-régression : le singulier doit toujours matcher."""
    resultat = classer(service, titre="Formation Excel et Word (bureautique)")

    assert resultat["domain"] == "bureautique"
