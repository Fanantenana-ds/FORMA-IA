# scripts/test_phase4_diag2.py
# ============================================================
# Scores BRUTS (seuil_min=0.0) pour trouver le seuil naturel
# ============================================================

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.rag.recherche_service import rechercher, RAG_MIN_SCORE_DEFAUT


QUESTIONS_PERTINENTES = [
    "Comment valider une relance de facture ?",
    "Quelles sont les étapes du module Veille ?",
    "Comment fonctionne le HITL ?",
    "Comment fonctionne le module TDR ?",
    "À quoi sert le module Préparation ?",
]

QUESTIONS_HORS_SUJET = [
    "Qu'est-ce que la blockchain ?",
    "Comment cuisiner une pizza ?",
    "Qui a gagné la Coupe du monde 2022 ?",
]


async def scores(question):
    try:
        resultats = await rechercher(
            question, top_k=3, collection="aide_plateforme",
            seuil_min=0.0, attente_max_s=30.0,
        )
    except Exception as exc:
        print(f"   ❌ {type(exc).__name__} — {exc}")
        return []
    return resultats


async def main():
    print("=" * 70)
    print(f"SCORES BRUTS — seuil_min=0.0  (défaut CDC : {RAG_MIN_SCORE_DEFAUT})")
    print("=" * 70)

    print("\n### QUESTIONS PERTINENTES (attendu : score élevé) ###")
    max_pertinents = []
    for q in QUESTIONS_PERTINENTES:
        print(f"\n❓ {q}")
        rs = await scores(q)
        if not rs:
            continue
        for i, r in enumerate(rs, 1):
            print(f"   [{i}] {r.score:.4f}  {r.fichier}")
        max_pertinents.append(rs[0].score)

    print("\n### QUESTIONS HORS SUJET (attendu : score bas) ###")
    max_hors = []
    for q in QUESTIONS_HORS_SUJET:
        print(f"\n❓ {q}")
        rs = await scores(q)
        if not rs:
            continue
        for i, r in enumerate(rs, 1):
            print(f"   [{i}] {r.score:.4f}  {r.fichier}")
        max_hors.append(rs[0].score)

    print()
    print("=" * 70)
    print("RÉSUMÉ")
    print("=" * 70)
    if max_pertinents:
        print(f"Score MAX des questions pertinentes : "
              f"{max(max_pertinents):.4f}")
        print(f"Score MIN des questions pertinentes : "
              f"{min(max_pertinents):.4f}")
    if max_hors:
        print(f"Score MAX des questions hors sujet  : "
              f"{max(max_hors):.4f}")
    if max_pertinents and max_hors:
        gap_min = min(max_pertinents)
        gap_max = max(max_hors)
        if gap_min > gap_max:
            seuil_conseille = round((gap_min + gap_max) / 2, 2)
            print()
            print(f"✅ SÉPARATION NETTE entre {gap_max:.4f} et {gap_min:.4f}")
            print(f"   → seuil conseillé : {seuil_conseille}")
        else:
            print()
            print(f"⚠️ PAS de séparation nette "
                  f"(pertinents min={gap_min:.4f}, "
                  f"hors-sujet max={gap_max:.4f})")


if __name__ == "__main__":
    asyncio.run(main())