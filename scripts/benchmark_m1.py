# scripts/benchmark_m1.py
# ============================================================
# BENCHMARK M1 — CLI (Étape C point 3, mission "Préparation soutenance")
# ============================================================
# Rejoue le corpus annoté à travers le pipeline M1 réel (VeilleOrchestrator
# .analyser_texte -> LLM réel si configuré) via BenchmarkRunner. AUCUNE
# donnée n'est inventée ici : le corpus vient de data/corpus_veille/, les
# résultats sont exactement ce que le pipeline a produit.
#
# --split dev|test   Ne garde que les entrées dont le champ "split" du
#                     corpus vaut cette valeur (absent tant que l'Étape D
#                     n'a pas ajouté ce champ au corpus -- ignoré avec un
#                     avertissement si aucune entrée n'a de "split").
# --limit N           Plafonne le nombre de documents traités.
# --reprendre         Retrouve le dernier résultat JSON déjà produit pour
#                     ce corpus/split, exclut les documents déjà traités,
#                     puis FUSIONNE l'ancien et le nouveau rapport
#                     (fusionner_rapports — équivalent à un run() unique
#                     sur l'union, aucune perte de précision).
#                     Limite assumée : ne protège pas une interruption EN
#                     PLEIN MILIEU d'un run() (rien n'est persisté avant
#                     la fin) -- pour un grand corpus, lancer par tranches
#                     avec --limit puis --reprendre entre chaque tranche.
# --pause SECONDES    Délai après CHAQUE document (courtoisie API/quota).
# --tranche N         Traite les documents par lots de N et ENREGISTRE le
#                     rapport fusionné après chaque lot (une interruption ne
#                     perd au plus qu'un lot). Si un lot contient un repli LLM
#                     ou une erreur modèle (signe probable d'un quota Groq
#                     épuisé), il est ÉCARTÉ et le run s'arrête : relancer
#                     plus tard avec --reprendre. 0 = un seul lot (ancien
#                     comportement).
#
# Estimation puis CONFIRMATION INTERACTIVE avant tout appel réel (aucun
# appel Groq sans accord explicite). Résultats JSON + CSV horodatés dans
# data/benchmark/results/.
#
# Exécution : python scripts/benchmark_m1.py [--split dev|test] [--limit N]
#             [--reprendre] [--pause 1.0] [--corpus chemin.jsonl]
# ============================================================

import argparse
import asyncio
import csv
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

RACINE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RACINE))

from dotenv import load_dotenv
load_dotenv(RACINE / ".env")

from app.services.benchmark.benchmark_runner import BenchmarkRunner, fusionner_rapports

RESULTS_DIR = RACINE / "data" / "benchmark" / "results"


def _filtrer_par_split(entries: list[dict[str, Any]], split: str | None) -> list[dict[str, Any]]:
    if split is None:
        return entries
    avec_split = [e for e in entries if "split" in e]
    if not avec_split:
        print(
            f"⚠️  Aucune entrée du corpus n'a de champ 'split' (Étape D pas encore faite) "
            f"— --split {split} ignoré, toutes les entrées sont utilisées."
        )
        return entries
    filtrees = [e for e in entries if e.get("split") == split]
    print(f"🔎 --split {split} : {len(filtrees)}/{len(entries)} entrée(s) retenue(s).")
    return filtrees


def _trouver_dernier_resultat(corpus_stem: str, split: str | None) -> Path | None:
    suffixe = f"_{split}" if split else ""
    motif = f"benchmark_m1_{corpus_stem}{suffixe}_*.json"
    candidats = sorted(RESULTS_DIR.glob(motif)) if RESULTS_DIR.exists() else []
    if not split:
        # Sans --split, ne reprendre QUE un rapport global : le motif
        # "..._*.json" attrape aussi "..._dev_*" et "..._test_*" (constat du 13/10).
        candidats = [c for c in candidats if not c.stem.startswith(
            (f"benchmark_m1_{corpus_stem}_dev_", f"benchmark_m1_{corpus_stem}_test_"))]
    return candidats[-1] if candidats else None


def _afficher_resume(r: dict[str, Any]) -> None:
    print("\n" + "=" * 70)
    print("📊 RÉSUMÉ DU BENCHMARK M1")
    print("=" * 70)
    print(f"   Documents testés       : {r['corpus_size_tested']}")
    print(f"   Précision détection    : {r['precision_detection']}")
    print(f"   Rappel détection       : {r['recall_detection']}")
    print(f"   F1 détection           : {r['f1_detection']}")
    print(f"   Exactitude domaine     : {r['domain_classification_accuracy']}")
    print(f"   F1 macro domaine       : {r['f1_macro_domain']}")
    print(f"   Exactitude extraction  : {r['extraction_accuracy']}")
    print(f"   Extraction par champ   : {r['extraction_par_champ']}")
    print(f"   Valeurs inventées      : {r['hallucinated_values']}")
    print(
        f"   Latence moy/méd/p95 (s): {r['average_latency_seconds']} / "
        f"{r['latency_median_seconds']} / {r['latency_p95_seconds']}"
    )
    print(f"   Replis LLM / erreurs   : {r['llm_fallback_count']} / {r['model_error_count']}")
    print(f"   Objectif précision >85%  atteint : {r['meets_cdc_precision']}")
    print(f"   Objectif extraction >90% atteint : {r['meets_cdc_extraction']}")
    print(f"   Objectif latence <3s     atteint : {r['meets_cdc_latency']}")
    if r["corpus_size_tested"] < 100:
        print(
            f"\n   ⚠️  {r['corpus_size_tested']} document(s) seulement — mesure INDICATIVE, "
            f"le CDC exige ≥100 documents annotés pour valider officiellement la précision."
        )
    print("=" * 70)


def _nom_resultat(corpus_stem: str, split: str | None) -> str:
    horodatage = datetime.now().strftime("%Y%m%d_%H%M%S")
    suffixe = f"_{split}" if split else ""
    return f"benchmark_m1_{corpus_stem}{suffixe}_{horodatage}"


def _ecrire_resultats(rapport: dict[str, Any], base_nom: str) -> None:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    chemin_json = RESULTS_DIR / f"{base_nom}.json"
    chemin_json.write_text(json.dumps(rapport, ensure_ascii=False, indent=2), encoding="utf-8")

    chemin_csv = RESULTS_DIR / f"{base_nom}.csv"
    with open(chemin_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            "id", "expected_is_opportunity", "predicted_is_opportunity",
            "correct_detection", "expected_domain", "predicted_domain",
            "latency_seconds", "erreur",
        ])
        for d in rapport["details"]:
            writer.writerow([
                d.get("id"), d.get("expected_is_opportunity"), d.get("predicted_is_opportunity"),
                d.get("correct_detection"), d.get("expected_domain"), d.get("predicted_domain"),
                d.get("latency_seconds"), d.get("erreur", ""),
            ])

    print(f"\n📝 Résultats JSON : {chemin_json}")
    print(f"📝 Détail CSV     : {chemin_csv}")


async def main() -> bool:
    parser = argparse.ArgumentParser(
        description="Benchmark M1 réel — mission 'Préparation soutenance', Étape C."
    )
    parser.add_argument("--split", choices=["dev", "test"], default=None)
    parser.add_argument("--limit", type=int, default=20)
    parser.add_argument("--reprendre", action="store_true")
    parser.add_argument("--pause", type=float, default=0.0, help="Secondes entre chaque document")
    parser.add_argument("--tranche", type=int, default=10,
                        help="Documents par lot, rapport enregistré après chaque lot (0 = un seul lot)")
    parser.add_argument("--corpus", default=None, help="Chemin corpus (sinon data/corpus_veille/corpus_v1.jsonl)")
    args = parser.parse_args()

    print("=" * 70)
    print("📊 BENCHMARK M1 — FORMA-IA")
    print("=" * 70)

    runner = BenchmarkRunner(corpus_path=Path(args.corpus) if args.corpus else None)
    try:
        toutes_entrees = runner._load_corpus(limit=None)
    except (FileNotFoundError, ValueError) as exc:
        print(f"❌ {exc}")
        return False

    entries = _filtrer_par_split(toutes_entrees, args.split)

    rapport_precedent: dict[str, Any] | None = None
    if args.reprendre:
        chemin_precedent = _trouver_dernier_resultat(runner.corpus_path.stem, args.split)
        if chemin_precedent:
            rapport_precedent = json.loads(chemin_precedent.read_text(encoding="utf-8"))
            ids_deja_traites = {d["id"] for d in rapport_precedent["details"]}
            avant = len(entries)
            entries = [e for e in entries if e.get("id") not in ids_deja_traites]
            print(
                f"🔁 --reprendre : {avant - len(entries)} déjà traité(s) "
                f"(voir {chemin_precedent.name}), {len(entries)} restant(s)."
            )
        else:
            print("ℹ️  --reprendre : aucun résultat précédent trouvé pour ce corpus/split — départ à zéro.")

    entries = entries[: args.limit]

    if not entries:
        print("\n✅ Rien à traiter (corpus vide après filtrage, ou tout déjà fait).")
        if rapport_precedent:
            _afficher_resume(rapport_precedent)
        return True

    print("\n" + "=" * 70)
    print("📊 ESTIMATION AVANT TOUT APPEL RÉEL")
    print("=" * 70)
    print(f"   Documents à traiter  : {len(entries)}")
    print(f"   Appels LLM estimés   : ~{len(entries)} (davantage si repli par lots sur certains documents)")
    print(f"   Pause entre documents: {args.pause}s")
    print(f"   Taille des lots      : {args.tranche or len(entries)} (sauvegarde après chaque lot)")
    print("=" * 70)

    try:
        reponse = input(f"\n❓ Lancer le benchmark RÉEL sur {len(entries)} document(s) ? [o/N] ").strip().lower()
    except EOFError:
        print("\n❌ Entrée non interactive — benchmark annulé (aucune confirmation possible).")
        return False

    if reponse not in ("o", "oui", "y", "yes"):
        print("❌ Benchmark annulé par l'utilisateur.")
        return False

    taille = args.tranche if args.tranche > 0 else len(entries)
    base_nom = _nom_resultat(runner.corpus_path.stem, args.split)
    rapport_final = rapport_precedent
    arret_anticipe = False

    for debut in range(0, len(entries), taille):
        lot = entries[debut:debut + taille]
        print(f"\n>> Lot {debut // taille + 1} : documents {debut + 1} à {debut + len(lot)} sur {len(entries)}...")
        rapport_lot = await runner.run(limit=len(lot), entries=lot, pause_secondes=args.pause)

        if rapport_lot["llm_fallback_count"] or rapport_lot["model_error_count"]:
            print(
                f"\n⛔ Lot écarté : {rapport_lot['llm_fallback_count']} repli(s) LLM, "
                f"{rapport_lot['model_error_count']} erreur(s) modèle — quota Groq probablement épuisé. "
                f"Ces documents ne sont PAS comptés. Relancez plus tard avec --reprendre."
            )
            arret_anticipe = True
            break

        rapport_final = fusionner_rapports([rapport_final, rapport_lot]) if rapport_final else rapport_lot
        _ecrire_resultats(rapport_final, base_nom)
        print(f"   ✅ Progression enregistrée : {rapport_final['corpus_size_tested']} document(s) au total.")

    if rapport_final:
        _afficher_resume(rapport_final)
    if arret_anticipe:
        return False

    return True


if __name__ == "__main__":
    ok = asyncio.run(main())
    sys.exit(0 if ok else 1)
