# scripts/importer_corpus.py
# ============================================================
# IMPORT DU CORPUS RÉEL — Module RAG (C3, Étape I)
# ============================================================
# Lit un dossier structuré (corpus_altiora/) et son formations.yaml,
# affiche D'ABORD l'estimation (tokens, requêtes, durée), DEMANDE
# CONFIRMATION, puis indexe via LE MÊME PIPELINE que l'API
# (RagOrchestrator.ingerer_fichier — extraction, nettoyage, découpage,
# Voyage, insertion, résumés) — aucune logique d'indexation dupliquée ici.
#
# STRUCTURE ATTENDUE (décision documentée — le format exact de
# formations.yaml n'était pas spécifié dans la mission au-delà de
# l'exemple d'arborescence ; association DOSSIER -> formation_code rendue
# EXPLICITE plutôt que supposée depuis le nom du dossier, pour éviter un
# mauvais rattachement silencieux) :
#
#   corpus_altiora/
#   ├── formations.yaml      (voir exemple ci-dessous)
#   ├── IA_FONDAMENTAUX/     (.pdf, .docx, .pptx, .xlsx, .txt)
#   ├── PYTHON_DATA/
#   └── ...
#
#   # corpus_altiora/formations.yaml
#   formations:
#     - dossier: IA_FONDAMENTAUX
#       formation_code: IA_FONDAMENTAUX
#       collection: support        # optionnel, défaut "support"
#     - dossier: PYTHON_DATA
#       formation_code: PYTHON_DATA
#
# Chaque formation_code DOIT déjà exister dans
# data/rag/catalogue_formations.yaml (le catalogue officiel FORMA-IA) —
# erreur claire et arrêt sinon, jamais un rattachement inventé.
#
# Options :
#   --echantillon N   Limite l'import aux N premiers fichiers (test avant
#                      un import complet).
#   --reprendre        N'estime/n'indexe que les fichiers PAS ENCORE
#                      indexés (idempotence déjà garantie par le pipeline
#                      via le hash SHA-256 ; cette option sert surtout à
#                      donner une estimation JUSTE du travail restant).
#
# Exécution : python scripts/importer_corpus.py chemin/vers/corpus_altiora
# ============================================================

import argparse
import asyncio
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from dotenv import load_dotenv

RACINE = Path(__file__).resolve().parents[1]
load_dotenv(RACINE / ".env")

import yaml

from app.services.rag.document_loader_service import (
    FORMATS_INDEXABLES, detect_file_type, extract_segments,
)
from app.services.rag.text_cleaner_service import clean_text
from app.services.rag.chunking_service import chunk_segments, chunk_pptx_slides
from app.services.rag.document_loader_service import Segment
from app.services.rag import registry_service as registre
from app.services.rag.catalogue_service import obtenir_formation
from app.orchestrator.rag_orchestrator import RagOrchestrator

EXTENSIONS_ACCEPTEES = set(FORMATS_INDEXABLES) | {"txt"}


def charger_formations_yaml(chemin_corpus: Path) -> List[Dict[str, str]]:
    chemin_yaml = chemin_corpus / "formations.yaml"
    if not chemin_yaml.exists():
        print(f"❌ Fichier introuvable : {chemin_yaml}")
        print("   Voir l'en-tête de ce script pour le format attendu.")
        sys.exit(1)

    with open(chemin_yaml, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}

    entrees = data.get("formations") or []
    if not entrees:
        print(f"❌ Aucune entrée 'formations:' dans {chemin_yaml}.")
        sys.exit(1)

    erreurs = []
    for entree in entrees:
        dossier = entree.get("dossier")
        code = entree.get("formation_code")
        if not dossier or not code:
            erreurs.append(f"Entrée incomplète (dossier et formation_code requis) : {entree}")
            continue
        if not (chemin_corpus / dossier).is_dir():
            erreurs.append(f"Dossier absent du corpus : '{dossier}'.")
            continue
        if obtenir_formation(code) is None:
            erreurs.append(
                f"formation_code '{code}' (dossier '{dossier}') absent de "
                f"data/rag/catalogue_formations.yaml — ajouter la formation au "
                f"catalogue AVANT d'importer, aucun rattachement inventé."
            )

    if erreurs:
        print("❌ formations.yaml invalide :")
        for e in erreurs:
            print(f"   - {e}")
        sys.exit(1)

    for entree in entrees:
        entree.setdefault("collection", "support")
    return entrees


def lister_fichiers(chemin_corpus: Path, formations: List[Dict[str, str]]) -> List[Tuple[Path, str, str]]:
    """Retourne [(chemin_fichier, formation_code, collection), ...]."""
    resultat = []
    for entree in formations:
        dossier = chemin_corpus / entree["dossier"]
        for chemin in sorted(dossier.rglob("*")):
            if chemin.is_file() and chemin.suffix.lstrip(".").lower() in EXTENSIONS_ACCEPTEES:
                resultat.append((chemin, entree["formation_code"], entree["collection"]))
    return resultat


def extraire_chunks_pour_estimation(chemin_fichier: Path) -> List[str]:
    """Reproduit extraction + nettoyage + découpage EXACTEMENT comme
    RagOrchestrator.ingerer_fichier() (aucun appel réseau, juste pour
    obtenir des textes de chunks fidèles à l'estimation)."""
    type_fichier = detect_file_type(str(chemin_fichier))
    try:
        segments = extract_segments(str(chemin_fichier), type_fichier)
    except Exception:
        return []
    if not segments:
        return []
    segments_propres = [Segment(numero=s.numero, texte=clean_text(s.texte)) for s in segments]
    chunks = chunk_pptx_slides(segments_propres) if type_fichier == "pptx" else chunk_segments(segments_propres)
    return [c.texte for c in chunks]


def main() -> bool:
    parser = argparse.ArgumentParser(description="Import du corpus réel FORMA-IA (Étape I, C3)")
    parser.add_argument("chemin_corpus", help="Dossier du corpus (contient formations.yaml)")
    parser.add_argument("--echantillon", type=int, default=None, help="Limite aux N premiers fichiers")
    parser.add_argument("--reprendre", action="store_true", help="N'estime/indexe que les fichiers pas encore indexés")
    args = parser.parse_args()

    chemin_corpus = Path(args.chemin_corpus).resolve()
    if not chemin_corpus.is_dir():
        print(f"❌ Dossier de corpus introuvable : {chemin_corpus}")
        return False

    print("=" * 70)
    print("📚 IMPORT DU CORPUS RÉEL — FORMA-IA (module C3, Étape I)")
    print("=" * 70)

    formations = charger_formations_yaml(chemin_corpus)
    print(f"\n📁 Corpus : {chemin_corpus}")
    print(f"🎓 {len(formations)} formation(s) déclarée(s) dans formations.yaml")

    fichiers = lister_fichiers(chemin_corpus, formations)
    print(f"📄 {len(fichiers)} fichier(s) trouvé(s) ({', '.join(sorted(EXTENSIONS_ACCEPTEES))})")

    if args.reprendre:
        avant = len(fichiers)
        fichiers = [
            (chemin, code, collection) for (chemin, code, collection) in fichiers
            if not registre.deja_indexe(registre.calculer_hash_fichier(str(chemin)))
        ]
        print(f"🔁 --reprendre : {avant - len(fichiers)} déjà indexé(s) exclu(s), {len(fichiers)} restant(s)")

    if args.echantillon is not None:
        fichiers = fichiers[: args.echantillon]
        print(f"🧪 --echantillon {args.echantillon} : import limité à {len(fichiers)} fichier(s)")

    if not fichiers:
        print("\n✅ Rien à importer (corpus vide ou tout déjà indexé).")
        return True

    print(f"\n⏳ Analyse de {len(fichiers)} fichier(s) (extraction + découpage, sans appel réseau)...")
    orchestrateur = RagOrchestrator()
    tous_les_textes: List[str] = []
    for chemin, _, _ in fichiers:
        tous_les_textes.extend(extraire_chunks_pour_estimation(chemin))

    if not tous_les_textes:
        print("\n⚠️ Aucun texte exploitable extrait des fichiers sélectionnés (formats non supportés, PDF scannés...).")
        print("   L'indexation réelle chargera chaque fichier individuellement et signalera la cause précise.")
    else:
        estimation = orchestrateur.estimer_cout(tous_les_textes)
        print("\n" + "=" * 70)
        print("📊 ESTIMATION AVANT INDEXATION")
        print("=" * 70)
        print(f"   Tokens estimés   : {estimation['tokens_estimes']:,}".replace(",", " "))
        print(f"   Requêtes Voyage  : {estimation['nb_requetes']}")
        print(f"   Durée estimée    : {estimation['duree_estimee_min']} min")
        if estimation["avertissement_duree"]:
            print("   ⚠️  Durée estimée > 15 min — import volontairement long, confirmer en connaissance de cause.")

    print("\n" + "=" * 70)
    try:
        reponse = input(f"❓ Confirmer l'indexation de {len(fichiers)} fichier(s) ? [o/N] ").strip().lower()
    except EOFError:
        print("\n❌ Entrée non interactive — import annulé (aucune confirmation possible).")
        return False

    if reponse not in ("o", "oui", "y", "yes"):
        print("❌ Import annulé par l'utilisateur.")
        return False

    print(f"\n⏳ Indexation de {len(fichiers)} fichier(s) — même pipeline que l'API (POST /ia/rag/indexer-document)...")
    debut = time.perf_counter()
    rapport = []
    for i, (chemin, formation_code, collection) in enumerate(fichiers, 1):
        print(f"   [{i}/{len(fichiers)}] {chemin.name}...")
        resultat = asyncio.run(orchestrateur.ingerer_fichier(str(chemin), formation_code, collection))
        rapport.append(resultat)
        print(f"        -> {resultat['statut']}" + (f" ({resultat.get('nb_chunks', '?')} chunks)" if resultat["statut"] == "indexe" else f" — {resultat.get('message', '')}"))

    duree_s = time.perf_counter() - debut

    print("\n" + "=" * 70)
    print("📋 RAPPORT FINAL")
    print("=" * 70)
    nb_indexes = sum(1 for r in rapport if r["statut"] == "indexe")
    nb_deja = sum(1 for r in rapport if r["statut"] == "deja_indexe")
    nb_erreurs = sum(1 for r in rapport if r["statut"] not in ("indexe", "deja_indexe"))
    print(f"   Indexés          : {nb_indexes}")
    print(f"   Déjà indexés     : {nb_deja}")
    print(f"   Erreurs/refusés  : {nb_erreurs}")
    print(f"   Durée réelle     : {duree_s / 60:.1f} min")
    if nb_erreurs:
        print("\n   Détail des erreurs :")
        for r in rapport:
            if r["statut"] not in ("indexe", "deja_indexe"):
                print(f"     - {r['fichier']} : {r['statut']} — {r.get('message', '')}")

    print("\n✅ IMPORT TERMINÉ." if nb_erreurs == 0 else "\n⚠️ IMPORT TERMINÉ AVEC ERREURS (voir détail ci-dessus).")
    print("=" * 70)
    return nb_erreurs == 0


if __name__ == "__main__":
    ok = main()
    sys.exit(0 if ok else 1)
