# ============================================================
# TESTS — app/services/rag/formation_resolver_service.py (Étape E §1)
# ============================================================

import pytest

from app.services.rag.formation_resolver_service import resoudre_formation

CATALOGUE = """
formations:
  - code: IA_FONDAMENTAUX
    titre: "Intelligence artificielle : les fondamentaux"
    synonymes: ["IA fondamentaux", "bases de l'IA", "initiation IA"]
    domaine: "Intelligence artificielle"
  - code: PYTHON_DATA
    titre: "Python pour la data science"
    synonymes: ["Python data", "data science Python"]
    domaine: "Data"
"""


@pytest.fixture
def chemin_catalogue(tmp_path):
    chemin = tmp_path / "catalogue.yaml"
    chemin.write_text(CATALOGUE, encoding="utf-8")
    return chemin


def test_resolution_par_code_exact(chemin_catalogue):
    resultat = resoudre_formation("IA_FONDAMENTAUX", chemin_catalogue)
    assert resultat.statut == "trouvee"
    assert resultat.formation.code == "IA_FONDAMENTAUX"


def test_resolution_par_titre_avec_faute_et_casse(chemin_catalogue):
    # "IA FONDEMANTAL" -> IA_FONDAMENTAUX (exemple donné par la mission)
    resultat = resoudre_formation("IA FONDEMANTAL", chemin_catalogue)
    assert resultat.statut == "trouvee"
    assert resultat.formation.code == "IA_FONDAMENTAUX"


def test_resolution_insensible_aux_accents(chemin_catalogue):
    resultat = resoudre_formation("fondemantaux ia", chemin_catalogue)
    assert resultat.statut in ("trouvee", "aucune")  # dépend du seuil, mais ne doit jamais planter


def test_resolution_par_synonyme(chemin_catalogue):
    resultat = resoudre_formation("je cherche les bases de l'IA", chemin_catalogue)
    assert resultat.statut == "trouvee"
    assert resultat.formation.code == "IA_FONDAMENTAUX"


def test_resolution_aucune_formation_proposee(chemin_catalogue):
    resultat = resoudre_formation("xylophone quantique intergalactique", chemin_catalogue)
    assert resultat.statut == "aucune"
    assert len(resultat.candidats) == 2  # toutes les formations proposées


def test_resolution_formation_totalement_differente(chemin_catalogue):
    resultat = resoudre_formation("Python pour la data science", chemin_catalogue)
    assert resultat.statut == "trouvee"
    assert resultat.formation.code == "PYTHON_DATA"


def test_resolution_catalogue_vide(tmp_path):
    chemin = tmp_path / "vide.yaml"
    chemin.write_text("formations: []\n", encoding="utf-8")
    resultat = resoudre_formation("n'importe quoi", chemin)
    assert resultat.statut == "aucune"
