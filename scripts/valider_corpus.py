# scripts/valider_corpus.py
# ============================================================
# VALIDATION DU CORPUS ANNOTÉ — Benchmark M1 (Étape 2, mission annotation)
# ============================================================
# Vérifie STRUCTURELLEMENT le corpus annoté (data/corpus_veille/corpus_v1.jsonl
# par défaut) : lecture seule, AUCUNE donnée n'est écrite, générée ni
# inventée ici. Complète scripts/../docs/protocole_annotation_corpus_m1.md.
#
# Vérifications, dans l'ordre, par ligne :
#   - JSON valide
#   - "id" présent, non vide, UNIQUE dans tout le fichier
#   - "raw_text" présent, non vide, longueur raisonnable (>= 20 caractères)
#   - "gold" est un objet, "gold.is_opportunity" est un booléen
#   - si is_opportunity=true : "gold.domain" présent et reconnu par le
#     classifieur (ia/data/devops/developpement/bureautique/autre) —
#     sinon domain_classification_accuracy serait faussé silencieusement
#   - budget_expected / deadline_expected / organizer_expected, si
#     présents, sont des chaînes non vides (jamais null/"" — une clé
#     présente doit vouloir dire "ceci doit être extrait")
#   - deadline_expected, si présent, est parseable en ISO 8601 (sinon
#     ATTENTION, pas bloquant : benchmark_runner.py retombe sur une
#     comparaison textuelle, voir _dates_concordent)
#
# Puis un résumé de couverture (total, équilibre positif/négatif,
# répartition par domaine) par rapport au seuil CDC de 100 documents.
#
# Affichage "[ÉTAPE] Vérification ... OK/ATTENTION/ÉCHEC" + détail, même
# convention que scripts/diagnostic_rag.py. Code de sortie 0 si aucune
# ÉCHEC structurelle, 1 sinon. Journal JSON horodaté dans logs/.
#
# Exécution : python scripts/valider_corpus.py [chemin_corpus]
# ============================================================

import json
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Tuple

RACINE = Path(__file__).resolve().parents[1]
DEFAULT_CORPUS_PATH = RACINE / "data" / "corpus_veille" / "corpus_v1.jsonl"

DOMAINES_RECONNUS = {"ia", "data", "devops", "developpement", "bureautique", "autre"}
LONGUEUR_MIN_RAW_TEXT = 20
SEUIL_CDC_NB_DOCUMENTS = 100
# "null" (Python None) ET l'absence de clé sont STRICTEMENT ÉQUIVALENTS pour
# benchmark_runner.py (dict.get("champ") renvoie None dans les deux cas) —
# vérifié sur le corpus réel existant (corpus-0002, budget_expected: null,
# annoté intentionnellement "pour tester l'extraction partielle"). Seules
# une chaîne vide ou un texte-placeholder sont de VRAIES erreurs d'annotation
# (valeur ambiguë, pouvant être confondue avec une extraction réelle).
VALEURS_INTERDITES_POUR_CHAMP_PRESENT = ("", "Non précisé")

OK, ATTENTION, ECHEC = "OK", "ATTENTION", "ÉCHEC"


def _afficher(nom: str, statut: str, message: str) -> None:
    symbole = {"OK": "✅", "ATTENTION": "⚠️ ", "ÉCHEC": "❌"}[statut]
    print(f"[ÉTAPE] Vérification {nom} ..... {statut} {symbole}")
    if message:
        print(f"        {message}")


def _charger_lignes_brutes(chemin: Path) -> List[str]:
    with open(chemin, "r", encoding="utf-8") as f:
        return [ligne.rstrip("\n") for ligne in f if ligne.strip()]


def _valider_ligne(numero: int, brut: str) -> Tuple[Dict[str, Any], List[str], List[str]]:
    """Retourne (entrée parsée ou {}, erreurs bloquantes, avertissements)."""
    erreurs: List[str] = []
    avertissements: List[str] = []

    try:
        entree = json.loads(brut)
    except json.JSONDecodeError as exc:
        return {}, [f"ligne {numero} : JSON invalide ({exc})"], []

    if not isinstance(entree, dict):
        return {}, [f"ligne {numero} : doit être un objet JSON, pas {type(entree).__name__}"], []

    id_doc = entree.get("id")
    if not id_doc or not isinstance(id_doc, str):
        erreurs.append(f"ligne {numero} : 'id' manquant ou vide")

    raw_text = entree.get("raw_text")
    if not isinstance(raw_text, str) or len(raw_text.strip()) < LONGUEUR_MIN_RAW_TEXT:
        erreurs.append(
            f"ligne {numero} (id={id_doc!r}) : 'raw_text' manquant ou trop court "
            f"(< {LONGUEUR_MIN_RAW_TEXT} caractères)"
        )

    gold = entree.get("gold")
    if not isinstance(gold, dict):
        erreurs.append(f"ligne {numero} (id={id_doc!r}) : 'gold' manquant ou n'est pas un objet")
        return entree, erreurs, avertissements

    is_opportunity = gold.get("is_opportunity")
    if not isinstance(is_opportunity, bool):
        erreurs.append(
            f"ligne {numero} (id={id_doc!r}) : 'gold.is_opportunity' doit être un booléen "
            f"(true/false), reçu {is_opportunity!r}"
        )

    domaine = gold.get("domain")
    if is_opportunity is True:
        if domaine is None:
            erreurs.append(
                f"ligne {numero} (id={id_doc!r}) : 'gold.domain' requis quand "
                f"is_opportunity=true"
            )
        elif domaine not in DOMAINES_RECONNUS:
            erreurs.append(
                f"ligne {numero} (id={id_doc!r}) : domaine '{domaine}' non reconnu "
                f"(attendu : {sorted(DOMAINES_RECONNUS)})"
            )

    for champ in ("budget_expected", "deadline_expected", "organizer_expected"):
        if champ in gold:
            valeur = gold[champ]
            if valeur in VALEURS_INTERDITES_POUR_CHAMP_PRESENT:
                erreurs.append(
                    f"ligne {numero} (id={id_doc!r}) : 'gold.{champ}' = {valeur!r} — "
                    f"utiliser null (rien à extraire) ou une valeur réelle, jamais une "
                    f"chaîne vide ni un texte-placeholder (voir protocole §2)"
                )

    deadline = gold.get("deadline_expected")
    if isinstance(deadline, str) and deadline.strip():
        try:
            datetime.fromisoformat(deadline.strip())
        except ValueError:
            avertissements.append(
                f"ligne {numero} (id={id_doc!r}) : 'gold.deadline_expected' = {deadline!r} "
                f"n'est pas au format ISO AAAA-MM-JJ (comparaison textuelle en repli, "
                f"moins fiable — voir protocole §2)"
            )

    return entree, erreurs, avertissements


def main(chemin_corpus: Path) -> bool:
    print("=" * 70)
    print("📋 VALIDATION DU CORPUS ANNOTÉ — Benchmark M1")
    print("=" * 70)

    if not chemin_corpus.exists():
        _afficher("fichier corpus", ECHEC, f"Introuvable : {chemin_corpus}")
        return False

    lignes_brutes = _charger_lignes_brutes(chemin_corpus)
    _afficher("fichier corpus", OK, f"{chemin_corpus} — {len(lignes_brutes)} ligne(s) non vide(s)")

    entrees: List[Dict[str, Any]] = []
    toutes_erreurs: List[str] = []
    tous_avertissements: List[str] = []
    ids_vus: Counter = Counter()

    for numero, brut in enumerate(lignes_brutes, start=1):
        entree, erreurs, avertissements = _valider_ligne(numero, brut)
        toutes_erreurs.extend(erreurs)
        tous_avertissements.extend(avertissements)
        if entree:
            entrees.append(entree)
            id_doc = entree.get("id")
            if id_doc:
                ids_vus[id_doc] += 1

    doublons = [id_doc for id_doc, nb in ids_vus.items() if nb > 1]
    if doublons:
        toutes_erreurs.append(f"identifiants dupliqués : {sorted(doublons)}")

    if toutes_erreurs:
        _afficher(
            "structure des entrées", ECHEC,
            f"{len(toutes_erreurs)} erreur(s) bloquante(s) :",
        )
        for erreur in toutes_erreurs:
            print(f"          - {erreur}")
    else:
        _afficher("structure des entrées", OK, f"{len(entrees)} entrée(s) valide(s).")

    if tous_avertissements:
        _afficher(
            "avertissements (non bloquants)", ATTENTION,
            f"{len(tous_avertissements)} point(s) à vérifier :",
        )
        for avertissement in tous_avertissements:
            print(f"          - {avertissement}")

    # --------------------------------------------------------
    # COUVERTURE
    # --------------------------------------------------------
    total = len(entrees)
    positifs = [e for e in entrees if e.get("gold", {}).get("is_opportunity") is True]
    negatifs = [e for e in entrees if e.get("gold", {}).get("is_opportunity") is False]
    domaines_couverts = Counter(
        e["gold"]["domain"] for e in positifs if e.get("gold", {}).get("domain")
    )

    print("\n" + "=" * 70)
    print("📊 COUVERTURE DU CORPUS")
    print("=" * 70)
    print(f"   Total documents      : {total} (seuil CDC : ≥ {SEUIL_CDC_NB_DOCUMENTS})")
    print(f"   Positifs / négatifs  : {len(positifs)} / {len(negatifs)}")
    print(f"   Domaines couverts    : {dict(domaines_couverts)}")

    domaines_absents = DOMAINES_RECONNUS - set(domaines_couverts)
    if domaines_absents:
        print(f"   ⚠️  Domaines sans aucun exemple positif : {sorted(domaines_absents)}")

    if total < SEUIL_CDC_NB_DOCUMENTS:
        _afficher(
            "seuil CDC (≥100 documents)", ATTENTION,
            f"{total}/{SEUIL_CDC_NB_DOCUMENTS} — il manque {SEUIL_CDC_NB_DOCUMENTS - total} document(s).",
        )
    else:
        _afficher("seuil CDC (≥100 documents)", OK, f"{total}/{SEUIL_CDC_NB_DOCUMENTS} atteint.")

    if total > 0:
        ratio_positifs = len(positifs) / total
        if not (0.3 <= ratio_positifs <= 0.7):
            _afficher(
                "équilibre positifs/négatifs", ATTENTION,
                f"{ratio_positifs:.0%} de positifs — un corpus déséquilibré rend la "
                f"précision moins représentative (voir protocole §3).",
            )
        else:
            _afficher("équilibre positifs/négatifs", OK, f"{ratio_positifs:.0%} de positifs.")

    succes = not toutes_erreurs

    print("\n" + "=" * 70)
    print("✅ VALIDATION STRUCTURELLE RÉUSSIE." if succes else "❌ VALIDATION ÉCHOUÉE (voir erreurs ci-dessus).")
    print("=" * 70)

    dossier_logs = RACINE / "logs"
    dossier_logs.mkdir(parents=True, exist_ok=True)
    horodatage = datetime.now().strftime("%Y%m%d_%H%M%S")
    chemin_journal = dossier_logs / f"validation_corpus_{horodatage}.json"
    with open(chemin_journal, "w", encoding="utf-8") as f:
        json.dump(
            {
                "horodatage": datetime.now().isoformat(),
                "corpus": str(chemin_corpus),
                "succes": succes,
                "total_documents": total,
                "positifs": len(positifs),
                "negatifs": len(negatifs),
                "domaines_couverts": dict(domaines_couverts),
                "erreurs": toutes_erreurs,
                "avertissements": tous_avertissements,
            },
            f, ensure_ascii=False, indent=2,
        )
    print(f"📝 Journal : {chemin_journal}")

    return succes


if __name__ == "__main__":
    chemin = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_CORPUS_PATH
    ok = main(chemin)
    sys.exit(0 if ok else 1)
