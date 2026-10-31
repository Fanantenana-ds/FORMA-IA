# ============================================================
# TESTS — app/services/rag/registry_service.py (Étape C §5-8)
# ============================================================
# Registre redirigé vers un fichier temporaire à chaque test : aucun
# fichier réel du projet n'est touché.
# ============================================================

import pytest

from app.services.rag import registry_service as registre


@pytest.fixture
def chemin_registre(tmp_path):
    return tmp_path / "index_registry.json"


def test_calculer_hash_fichier_deterministe(tmp_path):
    fichier = tmp_path / "a.txt"
    fichier.write_bytes(b"contenu identique")
    fichier2 = tmp_path / "b.txt"
    fichier2.write_bytes(b"contenu identique")

    assert registre.calculer_hash_fichier(str(fichier)) == registre.calculer_hash_fichier(str(fichier2))


def test_calculer_hash_fichier_differe_si_contenu_differe(tmp_path):
    a = tmp_path / "a.txt"
    a.write_bytes(b"contenu A")
    b = tmp_path / "b.txt"
    b.write_bytes(b"contenu B")

    assert registre.calculer_hash_fichier(str(a)) != registre.calculer_hash_fichier(str(b))


def test_deja_indexe_faux_si_jamais_vu(chemin_registre):
    assert registre.deja_indexe("hash-inconnu", chemin_registre) is False


def test_deja_indexe_vrai_apres_marquer_termine(chemin_registre):
    registre.initialiser_entree("h1", "doc.pdf", "IA_FONDAMENTAUX", chemin=chemin_registre)
    registre.marquer_termine("h1", nb_pages=3, nb_chunks=5, tokens_estimes=1000, modele_embed="voyage-4-large", chemin=chemin_registre)

    assert registre.deja_indexe("h1", chemin_registre) is True


def test_deja_indexe_faux_si_statut_erreur(chemin_registre):
    registre.marquer_statut_special("h2", "doc.pdf", "IA_FONDAMENTAUX", "erreur", "Échec test", chemin=chemin_registre)

    assert registre.deja_indexe("h2", chemin_registre) is False


def test_initialiser_entree_idempotente(chemin_registre):
    e1 = registre.initialiser_entree("h3", "doc.pdf", "IA_FONDAMENTAUX", chemin=chemin_registre)
    registre.marquer_lot_termine("h3", 2, chemin=chemin_registre)

    e2 = registre.initialiser_entree("h3", "doc.pdf", "IA_FONDAMENTAUX", chemin=chemin_registre)

    assert e2.dernier_lot_termine == 2  # pas réinitialisée (reprise après interruption)


def test_marquer_lot_termine_permet_la_reprise(chemin_registre):
    registre.initialiser_entree("h4", "gros.pdf", "IA_FONDAMENTAUX", chemin=chemin_registre)

    registre.marquer_lot_termine("h4", 0, chemin=chemin_registre)
    registre.marquer_lot_termine("h4", 1, chemin=chemin_registre)

    entree = registre.obtenir_entree("h4", chemin_registre)
    assert entree.dernier_lot_termine == 1
    assert entree.statut == "en_cours"


def test_marquer_statut_special_valide_le_statut(chemin_registre):
    with pytest.raises(ValueError):
        registre.marquer_statut_special("h5", "x.jpg", None, "statut_invalide", "message", chemin=chemin_registre)


def test_marquer_statut_special_non_indexable_image(chemin_registre):
    registre.marquer_statut_special("h6", "photo.jpg", None, "non_indexable_image", "Image seule.", chemin=chemin_registre)

    entree = registre.obtenir_entree("h6", chemin_registre)
    assert entree.statut == "non_indexable_image"
    assert entree.message == "Image seule."


def test_supprimer_entree(chemin_registre):
    registre.initialiser_entree("h7", "doc.pdf", "IA_FONDAMENTAUX", chemin=chemin_registre)
    registre.supprimer_entree("h7", chemin_registre)

    assert registre.obtenir_entree("h7", chemin_registre) is None


def test_entrees_pour_formation(chemin_registre):
    registre.initialiser_entree("h8", "a.pdf", "IA_FONDAMENTAUX", chemin=chemin_registre)
    registre.initialiser_entree("h9", "b.pdf", "PYTHON_DATA", chemin=chemin_registre)

    entrees = registre.entrees_pour_formation("IA_FONDAMENTAUX", chemin_registre)

    assert len(entrees) == 1
    assert entrees[0].hash == "h8"


def test_entrees_sans_resume(chemin_registre):
    registre.initialiser_entree("h10", "a.pdf", "IA_FONDAMENTAUX", chemin=chemin_registre)
    registre.marquer_termine("h10", nb_pages=1, nb_chunks=1, tokens_estimes=100, modele_embed="voyage-4-large", chemin=chemin_registre)
    # resume_statut reste "a_generer" par défaut (Groq jamais appelé dans ce test)

    entrees = registre.entrees_sans_resume(chemin_registre)

    assert len(entrees) == 1
    assert entrees[0].hash == "h10"


def test_registre_survit_a_un_rechargement(chemin_registre):
    registre.initialiser_entree("h11", "a.pdf", "IA_FONDAMENTAUX", chemin=chemin_registre)
    registre.marquer_termine("h11", nb_pages=2, nb_chunks=4, tokens_estimes=500, modele_embed="voyage-4-large", chemin=chemin_registre)

    # Simule un nouveau processus qui relit le fichier depuis le disque
    registre_recharge = registre.charger_registre(chemin_registre)

    assert "h11" in registre_recharge
    assert registre_recharge["h11"].nb_chunks == 4


def test_progression_conserve_compteurs_et_lit_ancien_registre(chemin_registre):
    import json

    chemin_registre.write_text(json.dumps({"h": {"hash": "h", "fichier": "ancien.pdf"}}))
    assert registre.obtenir_entree("h", chemin_registre).progression == {}
    registre.marquer_progression("h", "vectorisation", chemin_registre, chunks_prepares=8, chunks_indexes=0)
    registre.marquer_progression("h", "enregistrement", chemin_registre, lots_total=2)
    entry = registre.obtenir_entree("h", chemin_registre)
    assert entry.progression["chunks_prepares"] == 8
    assert entry.progression["chunks_indexes"] == 0
    assert entry.nb_chunks is None  # préparer ne signifie pas indexer
    assert entry.progression["etape"] == "enregistrement"


def test_erreur_de_progression_ne_signale_pas_un_succes(chemin_registre):
    registre.initialiser_entree("h", "doc.pdf", None, chemin=chemin_registre)
    registre.marquer_progression("h", "enregistrement", chemin_registre, chunks_prepares=8, chunks_indexes=3)
    registre.marquer_statut_special("h", "doc.pdf", None, "erreur", "Insertion refusée", chemin_registre)
    entry = registre.obtenir_entree("h", chemin_registre)
    assert entry.progression["chunks_indexes"] == 3
    assert entry.statut == "erreur"
    assert entry.progression["etape"] != "termine"
