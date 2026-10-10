# tests/unit/test_valider_corpus.py
# ============================================================
# Étape D (mission "Préparation soutenance") — valider_corpus.py v2
# ============================================================
# Teste les nouvelles règles de validation ajoutées au protocole v2 :
#   - champ "split" (dev|test) — ÉCHEC si valeur inconnue
#   - champ "type_opportunite" — ATTENTION si valeur non reconnue pour positif
#   - résumé de stratification dev/test dans main()
#   - ATTENTION si corpus partiellement annoté split (certaines entrées avec,
#     d'autres sans)
#   - les règles v1 existantes restent inchangées (non régressées)
#
# Aucun réseau, aucune donnée inventée — corpus JSONL synthétiques créés
# dans tmp_path.
# ============================================================

import importlib.util
import json
import sys
from pathlib import Path

import pytest

RACINE = Path(__file__).resolve().parents[2]


def _charger_module():
    chemin = RACINE / "scripts" / "valider_corpus.py"
    spec = importlib.util.spec_from_file_location("valider_corpus_sous_test", chemin)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


vc = _charger_module()


# ============================================================
# Helpers
# ============================================================

def _ecrire_corpus(tmp_path: Path, entrees: list) -> Path:
    chemin = tmp_path / "corpus.jsonl"
    with open(chemin, "w", encoding="utf-8") as f:
        for e in entrees:
            f.write(json.dumps(e, ensure_ascii=False) + "\n")
    return chemin


POSITIF_MINIMAL = {
    "id": "t01",
    "raw_text": "x" * 30,
    "gold": {"is_opportunity": True, "domain": "ia"},
}

NEGATIF_MINIMAL = {
    "id": "t02",
    "raw_text": "y" * 30,
    "gold": {"is_opportunity": False},
}


# ============================================================
# _valider_ligne — champ split v2
# ============================================================

def test_split_absent_pas_erreur():
    entree = {**POSITIF_MINIMAL}
    _, erreurs, _ = vc._valider_ligne(1, json.dumps(entree))
    assert not erreurs


def test_split_dev_valide():
    entree = {**POSITIF_MINIMAL, "split": "dev"}
    _, erreurs, _ = vc._valider_ligne(1, json.dumps(entree))
    assert not erreurs


def test_split_test_valide():
    entree = {**POSITIF_MINIMAL, "split": "test"}
    _, erreurs, _ = vc._valider_ligne(1, json.dumps(entree))
    assert not erreurs


def test_split_valeur_inconnue_produit_une_erreur():
    entree = {**POSITIF_MINIMAL, "split": "validation"}
    _, erreurs, _ = vc._valider_ligne(1, json.dumps(entree))
    assert any("split" in e for e in erreurs)


def test_split_valeur_majuscules_produit_une_erreur():
    entree = {**POSITIF_MINIMAL, "split": "Dev"}
    _, erreurs, _ = vc._valider_ligne(1, json.dumps(entree))
    assert any("split" in e for e in erreurs)


# ============================================================
# _valider_ligne — champ type_opportunite v2
# ============================================================

def test_type_opportunite_absent_pas_erreur():
    entree = {**POSITIF_MINIMAL}
    _, erreurs, avertissements = vc._valider_ligne(1, json.dumps(entree))
    assert not erreurs
    assert not any("type_opportunite" in a for a in avertissements)


def test_type_opportunite_valide_appel_offres():
    entree = {**POSITIF_MINIMAL, "type_opportunite": "appel_offres"}
    _, erreurs, avertissements = vc._valider_ligne(1, json.dumps(entree))
    assert not erreurs
    assert not any("type_opportunite" in a for a in avertissements)


def test_type_opportunite_valide_tous_les_types_reconnus():
    for t in vc.TYPES_OPPORTUNITE_RECONNUS:
        entree = {**POSITIF_MINIMAL, "type_opportunite": t}
        _, erreurs, avertissements = vc._valider_ligne(1, json.dumps(entree))
        assert not erreurs, f"type '{t}' produit une erreur inattendue"
        noms = [a for a in avertissements if "type_opportunite" in a]
        assert not noms, f"type '{t}' produit un avertissement inattendu"


def test_type_opportunite_valeur_inconnue_produit_avertissement():
    entree = {**POSITIF_MINIMAL, "type_opportunite": "inconnu"}
    _, erreurs, avertissements = vc._valider_ligne(1, json.dumps(entree))
    assert not erreurs  # non bloquant
    assert any("type_opportunite" in a for a in avertissements)


def test_type_opportunite_sur_negatif_pas_avertissement():
    """type_opportunite n'est pertinent que pour les positifs."""
    entree = {**NEGATIF_MINIMAL, "type_opportunite": "inconnu"}
    _, erreurs, avertissements = vc._valider_ligne(1, json.dumps(entree))
    assert not erreurs
    assert not any("type_opportunite" in a for a in avertissements)


# ============================================================
# main() — stratification dev/test
# ============================================================

def test_main_corpus_sans_split_pas_de_section_stratification(tmp_path, capsys):
    chemin = _ecrire_corpus(tmp_path, [POSITIF_MINIMAL, NEGATIF_MINIMAL])
    vc.main(chemin)
    out = capsys.readouterr().out
    assert "STRATIFICATION" not in out


def test_main_corpus_avec_split_complet_affiche_stratification(tmp_path, capsys):
    entrees = [
        {**POSITIF_MINIMAL, "id": "a1", "split": "dev"},
        {**NEGATIF_MINIMAL, "id": "a2", "split": "dev"},
        {**POSITIF_MINIMAL, "id": "a3", "split": "test"},
        {**NEGATIF_MINIMAL, "id": "a4", "split": "test"},
    ]
    chemin = _ecrire_corpus(tmp_path, entrees)
    vc.main(chemin)
    out = capsys.readouterr().out
    assert "STRATIFICATION" in out
    assert "dev" in out
    assert "test" in out


def test_main_corpus_partiellement_annote_split_produit_attention(tmp_path, capsys):
    entrees = [
        {**POSITIF_MINIMAL, "id": "b1", "split": "dev"},
        {**NEGATIF_MINIMAL, "id": "b2"},  # pas de split
    ]
    chemin = _ecrire_corpus(tmp_path, entrees)
    vc.main(chemin)
    out = capsys.readouterr().out
    assert "ATTENTION" in out or "partiellement" in out.lower()


def test_main_stratification_desequilibree_produit_attention(tmp_path, capsys):
    """95 % en dev, 5 % en test → déséquilibre de stratification."""
    entrees = []
    for i in range(19):
        entrees.append({"id": f"d{i}", "raw_text": "x" * 30,
                        "gold": {"is_opportunity": True, "domain": "ia"}, "split": "dev"})
    entrees.append({"id": "t1", "raw_text": "x" * 30,
                    "gold": {"is_opportunity": True, "domain": "ia"}, "split": "test"})
    chemin = _ecrire_corpus(tmp_path, entrees)
    vc.main(chemin)
    out = capsys.readouterr().out
    # doit signaler un déséquilibre de stratification
    assert "ATTENTION" in out


# ============================================================
# Rétrocompatibilité v1 (non régression)
# ============================================================

def test_v1_corpus_toujours_valide(tmp_path, capsys):
    """Un corpus v1 sans aucun champ v2 doit passer sans erreur."""
    entrees = [
        {"id": "v1-01", "raw_text": "x" * 30, "gold": {"is_opportunity": True, "domain": "ia"}},
        {"id": "v1-02", "raw_text": "y" * 30, "gold": {"is_opportunity": False}},
    ]
    chemin = _ecrire_corpus(tmp_path, entrees)
    ok = vc.main(chemin)
    assert ok is True
