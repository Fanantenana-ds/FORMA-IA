# scripts/stats_chat.py
# ============================================================
# STATISTIQUES DU CHAT — data/rag/chat_logs.jsonl (Étape E §6)
# ============================================================
# Répartition par type, temps moyen/médian par type, taux de hors sujet,
# taux d'utilisation du cache.
#
# Exécution : python scripts/stats_chat.py
# ============================================================

import statistics
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.rag.chat_log_service import lire_toutes_les_lignes


def main() -> bool:
    print("=" * 70)
    print("📊 STATISTIQUES DU CHAT — FORMA-IA (RAG)")
    print("=" * 70)

    lignes = lire_toutes_les_lignes()
    if not lignes:
        print("\nℹ️ Aucune conversation journalisée pour l'instant.")
        return True

    total = len(lignes)
    par_type = defaultdict(list)
    for ligne in lignes:
        par_type[ligne.get("type_detecte", "?")].append(ligne)

    print(f"\n📋 {total} message(s) au total.\n")
    print(f"{'Type':<22} {'Nb':<6} {'%':<7} {'Moy. (ms)':<11} {'Médiane (ms)'}")
    print("-" * 65)

    for type_detecte, entrees in sorted(par_type.items(), key=lambda x: -len(x[1])):
        durees = [e["duree_ms"] for e in entrees if "duree_ms" in e]
        moyenne = statistics.mean(durees) if durees else 0
        mediane = statistics.median(durees) if durees else 0
        pourcentage = 100 * len(entrees) / total
        print(f"{type_detecte:<22} {len(entrees):<6} {pourcentage:<6.1f}% {moyenne:<11.1f} {mediane:.1f}")

    nb_hors_sujet = len(par_type.get("hors_sujet", []))
    taux_hors_sujet = 100 * nb_hors_sujet / total

    lignes_avec_voyage = [l for l in lignes if l.get("modele_requete")]
    nb_cache_utilise = sum(1 for l in lignes_avec_voyage if l.get("cache_utilise"))
    taux_cache = (100 * nb_cache_utilise / len(lignes_avec_voyage)) if lignes_avec_voyage else 0.0

    print("\n" + "=" * 70)
    print(f"🚫 Taux de hors sujet : {taux_hors_sujet:.1f}% ({nb_hors_sujet}/{total})")
    print(
        f"💾 Taux d'utilisation du cache (questions ayant appelé Voyage) : "
        f"{taux_cache:.1f}% ({nb_cache_utilise}/{len(lignes_avec_voyage)})"
    )
    print("=" * 70)
    return True


if __name__ == "__main__":
    succes = main()
    sys.exit(0 if succes else 1)
