import asyncio
import json
import logging
import sys
from pathlib import Path

from dotenv import load_dotenv
load_dotenv()
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
    datefmt="%H:%M:%S",
)

from app.services.formations.attestation_generator_service import (
    AttestationGeneratorService,
)


SESSION = {
    "id": 1,
    "titre": "Introduction à l'IA",
    "domaine": "IA",
    "niveau_cible": "Intermédiaire",
    "date_debut": "2026-10-15",
    "date_fin": "2026-10-16",
    "lieu": "Antananarivo",
    "formateur": "Rakoto",
    "duree_jours": 2,
}

PARTICIPANTS = [
    {"id": 1, "nom": "Jean Dupont", "genre": "M", "entreprise": "CFAO"},
    {"id": 2, "nom": "Marie Rasoa", "genre": "F", "entreprise": "BASAN"},
]


async def main():
    print("=" * 70)
    print("🧪 TEST AGENT 5 — AttestationGeneratorService")
    print("=" * 70)

    service = AttestationGeneratorService()

    # ── Test 1 : 1 participant ──
    print("\n🚀 [TEST 1] 1 participant...")
    result = await service.generate_one(SESSION, PARTICIPANTS[0], index=1)
    print(f"   ✅ N° : {result['numero_unique']}")
    print(f"   ✅ Source : {result['metadata']['source']}")
    print(f"   ✅ Compétences : {len(result['content']['competences'])}")

    # ── Test 2 : BATCH ──
    print("\n🚀 [TEST 2] BATCH (2 participants)...")
    batch = await service.generate_batch(SESSION, PARTICIPANTS)
    print(f"   ✅ Générées : {batch['total_generated']}/{batch['total_eligible']}")

    # ── Sauvegarde ──
    out = Path("outputs"); out.mkdir(exist_ok=True)
    f = out / "agent5_test_output.json"
    with open(f, "w", encoding="utf-8") as fp:
        json.dump({"single": result, "batch": batch}, fp, indent=2, ensure_ascii=False)
    print(f"\n💾 Sauvegardé : {f}")

    print("\n" + "=" * 70)
    print("✅ TEST TERMINÉ")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())