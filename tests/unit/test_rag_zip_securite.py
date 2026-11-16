# ============================================================
# TESTS — app/services/rag/zip_securite.py (Étape C §4)
# ============================================================
# Aucun réseau, aucune vraie base. Les seuils (200 Mo/500 Mo/200 fichiers)
# sont testés en les abaissant temporairement (monkeypatch) plutôt qu'en
# manipulant de vrais gigaoctets.
# ============================================================

import zipfile

import pytest

from app.services.rag import zip_securite


def _creer_zip(chemin, membres: dict, imbrique: bool = False):
    """membres = {nom_dans_le_zip: contenu_bytes}"""
    with zipfile.ZipFile(chemin, "w", zipfile.ZIP_DEFLATED) as zf:
        for nom, contenu in membres.items():
            zf.writestr(nom, contenu)


def test_zip_normal_accepte(tmp_path):
    chemin = tmp_path / "normal.zip"
    _creer_zip(chemin, {"a.pdf": b"contenu a", "b.docx": b"contenu b"})

    membres = zip_securite.verifier_et_lister(str(chemin))

    assert {m.nom for m in membres} == {"a.pdf", "b.docx"}


def test_zip_bombe_refuse(tmp_path, monkeypatch):
    monkeypatch.setattr(zip_securite, "MAX_DECOMPRESSE_OCTETS", 100)  # seuil abaissé pour le test
    chemin = tmp_path / "bombe.zip"
    _creer_zip(chemin, {"gros.txt": b"x" * 1000})  # dépasse le seuil abaissé

    with pytest.raises(zip_securite.ZipSecuriteError, match="décompressé"):
        zip_securite.verifier_et_lister(str(chemin))


def test_zip_trop_de_fichiers_refuse(tmp_path, monkeypatch):
    monkeypatch.setattr(zip_securite, "MAX_FICHIERS", 3)
    chemin = tmp_path / "trop.zip"
    _creer_zip(chemin, {f"fichier_{i}.txt": b"x" for i in range(5)})

    with pytest.raises(zip_securite.ZipSecuriteError, match="fichiers"):
        zip_securite.verifier_et_lister(str(chemin))


def test_zip_slip_chemin_double_point_refuse(tmp_path):
    chemin = tmp_path / "malveillant.zip"
    _creer_zip(chemin, {"../../etc/passwd": b"x"})

    with pytest.raises(zip_securite.ZipSecuriteError, match="non sûr"):
        zip_securite.verifier_et_lister(str(chemin))


def test_zip_slip_chemin_absolu_refuse(tmp_path):
    chemin = tmp_path / "malveillant2.zip"
    _creer_zip(chemin, {"/etc/passwd": b"x"})

    with pytest.raises(zip_securite.ZipSecuriteError, match="non sûr"):
        zip_securite.verifier_et_lister(str(chemin))


def test_zip_imbrique_refuse(tmp_path):
    chemin = tmp_path / "imbrique.zip"
    _creer_zip(chemin, {"interieur.zip": b"PK\x03\x04fausse archive"})

    with pytest.raises(zip_securite.ZipSecuriteError, match="imbriqué"):
        zip_securite.verifier_et_lister(str(chemin))


def test_zip_trop_volumineux_compresse_refuse(tmp_path, monkeypatch):
    monkeypatch.setattr(zip_securite, "MAX_COMPRESSE_OCTETS", 10)
    chemin = tmp_path / "gros_compresse.zip"
    _creer_zip(chemin, {"a.txt": b"contenu suffisant pour depasser 10 octets compresses"})

    with pytest.raises(zip_securite.ZipSecuriteError, match="volumineuse"):
        zip_securite.verifier_et_lister(str(chemin))


def test_zip_invalide_refuse(tmp_path):
    chemin = tmp_path / "pas_un_zip.zip"
    chemin.write_bytes(b"ceci n'est pas une archive ZIP")

    with pytest.raises(zip_securite.ZipSecuriteError, match="invalide"):
        zip_securite.verifier_et_lister(str(chemin))


def test_extraire_membre_ecrit_le_bon_contenu(tmp_path):
    chemin = tmp_path / "ok.zip"
    _creer_zip(chemin, {"doc.txt": b"contenu du document"})
    destination = tmp_path / "extraction"

    chemin_extrait = zip_securite.extraire_membre(str(chemin), "doc.txt", destination)

    assert chemin_extrait.read_bytes() == b"contenu du document"


def test_extraire_membre_chemin_dangereux_refuse(tmp_path):
    destination = tmp_path / "extraction"
    with pytest.raises(zip_securite.ZipSecuriteError):
        zip_securite.extraire_membre("peu importe.zip", "../../evasion.txt", destination)
