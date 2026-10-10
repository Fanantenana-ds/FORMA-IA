# scripts/test_phase4_recherche.py
# ============================================================
# TEST PHASE 4 — Recherche sémantique (pgvector + Voyage)
# ============================================================

import asyncio
import sys
from dataclasses import fields, is_dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.rag.recherche_service import rechercher


QUESTIONS = [
    "Comment valider une relance de facture ?",
    "Quelles sont les étapes du module Veille ?",
    "Comment fonctionne le HITL ?",
    "Qu'est-ce que la blockchain ?",   # hors sujet attendu
]


def afficher(r, i):
    """Affiche un resultat, dict ou dataclass."""
    if is_dataclass(r):
        noms = [f.name for f in fields(r)]
    elif isinstance(r, dict):
        noms = list(r.keys())
    else:
        print(f"   [{i}] type inconnu : {type(r).__name__}")
        return

    # Première fois : afficher les champs disponibles
    if i == 1:
        print(f"        (champs : {noms})")

    score = getattr(r, "score", None) if not isinstance(r, dict) else r.get("score")
    fichier = getattr(r, "fichier", None) if not isinstance(r, dict) else r.get("fichier")
    page = getattr(r, "page_debut", None) if not isinstance(r, dict) else r.get("page_debut")
    contenu = getattr(r, "contenu", None) if not isinstance(r, dict) else r.get("contenu")

    score_txt = f"{score:.4f}" if isinstance(score, (int, float)) else str(score)
    print(f"   [{i}] score={score_txt}  fichier={fichier}  page={page}")
    if contenu:
        extrait = contenu[:100].replace("\n", " ")
        print(f"       {extrait}...")


async def main():
    print("=" * 70)
    print("TEST PHASE 4 — RECHERCHE SÉMANTIQUE")
    print("=" * 70)

    for collection in ["aide_plateforme", None]:
        label = collection if collection else "TOUTES (collection=None)"
        print()
        print(f"### Collection : {label} ###")

        for q in QUESTIONS:
            print()
            print(f"❓ {q}")
            try:
                resultats = await rechercher(
                    q, top_k=3, collection=collection,
                )
            except Exception as exc:
                print(f"   ❌ ERREUR : {type(exc).__name__} — {exc}")
                continue

            if not resultats:
                print("   (aucun résultat au-dessus du seuil)")
                continue

            for i, r in enumerate(resultats, 1):
                afficher(r, i)

    print()
    print("=" * 70)
    print("PHASE 4 : OK")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())