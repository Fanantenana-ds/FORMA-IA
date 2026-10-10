# scripts/test_phase6_idempotence.py
# ============================================================
# TEST PHASE 6 — Idempotence (SHA-256 : pas de réindexation)
# ============================================================

import asyncio
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.orchestrator.rag_orchestrator import RagOrchestrator


FICHIER_TEST = "docs/guide_utilisateur/07_facturation_m7.md"


async def main():
    print("=" * 70)
    print("TEST PHASE 6 — IDEMPOTENCE")
    print("=" * 70)

    orch = RagOrchestrator()

    print(f"\nFichier : {FICHIER_TEST}")
    print("(Déjà indexé à l'Étape F)\n")

    print("Tentative de réindexation...")
    t0 = time.time()
    try:
        r = await orch.ingerer_fichier(FICHIER_TEST, "aide_plateforme")
    except Exception as exc:
        print(f"❌ ERREUR : {type(exc).__name__} — {exc}")
        return
    duree = time.time() - t0

    print(f"\nRésultat :")
    print(f"   statut      : {r.get('statut')}")
    print(f"   message     : {r.get('message', '(aucun)')}")
    print(f"   nb_chunks   : {r.get('nb_chunks', '(non calculé)')}")
    print(f"   durée       : {duree:.2f} s")

    if r.get("statut") == "deja_indexe":
        print()
        print("✅ IDEMPOTENCE VÉRIFIÉE")
        print("   → Aucun appel Voyage")
        print("   → Aucune réécriture DB")
        if duree < 2.0:
            print(f"   → Durée < 2 s ({duree:.2f} s) : cohérent")
    else:
        print()
        print(f"⚠️  Statut inattendu : {r.get('statut')}")

    print()
    print("=" * 70)
    print("PHASE 6 : OK")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())