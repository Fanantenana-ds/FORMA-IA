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
    {"id": 1, "nom": "Jean Dupont", "genre": "M", "entreprise": "Ministère"},
    {"id": 2, "nom": "Marie Rasoa", "genre": "F", "entreprise": "Ministère"},
]


async def main():
    print("=" * 70)
    print("🧪 TEST AGENT 5 — JSON + PDF (hybride)")
    print("=" * 70)

    service = AttestationGeneratorService()

    # ---- Test 1 : 1 participant + PDF ----
    print("\n🚀 [TEST 1] 1 participant + PDF...")
    r = await service.generate_one_with_pdf(SESSION, PARTICIPANTS[0], index=1)
    print(f"   ✅ N°        : {r['numero_unique']}")
    print(f"   ✅ Source    : {r['metadata']['source']}")
    print(f"   ✅ PDF généré: {r.get('pdf_generated')}")
    print(f"   ✅ PDF path  : {r.get('pdf_path')}")

    # ---- Test 2 : BATCH + PDF ----
    print("\n🚀 [TEST 2] BATCH (2 participants) + PDF...")
    b = await service.generate_batch_with_pdf(SESSION, PARTICIPANTS)
    print(f"   ✅ Contenus  : {b['total_generated']}/{b['total_eligible']}")
    print(f"   ✅ PDF       : {b['total_pdf_generated']}/{b['total_eligible']}")

    # ---- Sauvegarde JSON ----
    out = Path("outputs")
    out.mkdir(exist_ok=True)
    f = out / "agent5_pdf_test_output.json"
    with open(f, "w", encoding="utf-8") as fp:
        json.dump({"single": r, "batch": b}, fp, indent=2, ensure_ascii=False)
    print(f"\n💾 Sauvegardé : {f}")

    print("\n" + "=" * 70)
    print("✅ TEST TERMINÉ")
    print("=" * 70)
    print("\n📁 Vérifiez les PDF dans : exports/attestations/")


if __name__ == "__main__":
    asyncio.run(main())