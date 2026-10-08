# ============================================================
# TESTS — app/services/rag/catalogue_service.py
# ============================================================

import pytest

from app.services.rag import catalogue_service as catalogue

CATALOGUE_VALIDE = """
formations:
  - code: IA_FONDAMENTAUX
    titre: "Intelligence artificielle : les fondamentaux"
    domaine: "Intelligence artificielle"
    duree_jours: 3
    confidentiel: false
    synonymes: ["IA fondamentaux"]
    realisations:
      - client: "Ministère X"
        client_confidentiel: true
        secteur_public: "Administration publique"
        annee: 2025
  - code: PROJET_CONFIDENTIEL
    titre: "Formation confidentielle"
    confidentiel: true
    realisations: []
"""


@pytest.fixture
def chemin_catalogue(tmp_path):
    chemin = tmp_path / "catalogue.yaml"
    chemin.write_text(CATALOGUE_VALIDE, encoding="utf-8")
    return chemin


def test_charger_catalogue(chemin_catalogue):
    formations = catalogue.charger_catalogue(chemin_catalogue)
    assert len(formations) == 2
    assert formations[0].code == "IA_FONDAMENTAUX"


def test_obtenir_formation_insensible_a_la_casse(chemin_catalogue):
    formation = catalogue.obtenir_formation("ia_fondamentaux", chemin_catalogue)
    assert formation is not None
    assert formation.titre == "Intelligence artificielle : les fondamentaux"


def test_obtenir_formation_inconnue(chemin_catalogue):
    assert catalogue.obtenir_formation("INEXISTANTE", chemin_catalogue) is None


def test_realisation_affichage_client_confidentiel(chemin_catalogue):
    formation = catalogue.obtenir_formation("IA_FONDAMENTAUX", chemin_catalogue)
    assert formation.realisations[0].affichage_client() == "Administration publique"


def test_annee_la_plus_recente(chemin_catalogue):
    formation = catalogue.obtenir_formation("IA_FONDAMENTAUX", chemin_catalogue)
    assert formation.annee_la_plus_recente() == 2025


def test_catalogue_fichier_introuvable(tmp_path):
    with pytest.raises(catalogue.CatalogueFormationsError, match="introuvable"):
        catalogue.charger_catalogue(tmp_path / "n_existe_pas.yaml")


def test_catalogue_code_en_double_refuse(tmp_path):
    chemin = tmp_path / "doublon.yaml"
    chemin.write_text(
        "formations:\n"
        "  - code: X\n    titre: 'Un'\n"
        "  - code: X\n    titre: 'Deux'\n",
        encoding="utf-8",
    )
    with pytest.raises(catalogue.CatalogueFormationsError, match="double"):
        catalogue.charger_catalogue(chemin)


def test_formation_indexable_non_confidentielle(chemin_catalogue, monkeypatch):
    monkeypatch.delenv("VOYAGE_OPT_OUT", raising=False)
    formation = catalogue.obtenir_formation("IA_FONDAMENTAUX", chemin_catalogue)
    assert catalogue.formation_indexable(formation) is True


def test_formation_confidentielle_refusee_sans_opt_out(chemin_catalogue, monkeypatch):
    monkeypatch.delenv("VOYAGE_OPT_OUT", raising=False)
    formation = catalogue.obtenir_formation("PROJET_CONFIDENTIEL", chemin_catalogue)
    assert catalogue.formation_indexable(formation) is False


def test_formation_confidentielle_acceptee_avec_opt_out(chemin_catalogue, monkeypatch):
    monkeypatch.setenv("VOYAGE_OPT_OUT", "true")
    formation = catalogue.obtenir_formation("PROJET_CONFIDENTIEL", chemin_catalogue)
    assert catalogue.formation_indexable(formation) is True
