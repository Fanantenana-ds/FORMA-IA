
import asyncio
import json
import logging
import sys
import time
from pathlib import Path

# Charge .env
from dotenv import load_dotenv
load_dotenv()

# Ajoute la racine du projet au PYTHONPATH
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

# Configuration des logs
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
    datefmt="%H:%M:%S",
)

from app.services.formations.form_generator_service import FormGeneratorService


# ============================================================
# DONNÉES DE TEST
# ============================================================
SESSION_INFO = {
    "titre": "Introduction à l'IA",
    "domaine": "IA",
    "niveau_cible": "Intermédiaire",
    "date_debut": "2026-10-15",
    "date_fin": "2026-10-16",
    "lieu": "Antananarivo",
    "formateur": "Rakoto",
    "max_participants": 20,
    "public_cible": "Ministère de l'Éducation",
}


# ============================================================
# TEST
# ============================================================
async def main():
    print("=" * 70)
    print("🧪 TEST AGENT 1 — FormGeneratorService")
    print("=" * 70)

    # --- 1. Init service ---
    print("\n🔧 [1/4] Initialisation du service...")
    try:
        service = FormGeneratorService()
        print("   ✅ Service initialisé")
    except Exception as e:
        print(f"   ❌ Échec init : {e}")
        return

    # --- 2. Appel IA ---
    print("\n🚀 [2/4] Appel de l'IA (Groq)...")
    start = time.perf_counter()
    try:
        result = await service.generate(SESSION_INFO)
        elapsed = round(time.perf_counter() - start, 2)
        print(f"   ✅ Réponse reçue en {elapsed}s")
    except Exception as e:
        print(f"   ❌ Échec appel IA : {e}")
        return

    # --- 3. Vérification structure ---
    print("\n🔍 [3/4] Vérification de la structure...")
    sections = ["inscription", "test_avant", "test_apres", "satisfaction", "metadata"]
    ok = True
    for s in sections:
        if s in result:
            if s != "metadata":
                n = len(result[s].get("questions", []))
                print(f"   ✅ {s:15s} → {n} questions")
            else:
                print(f"   ✅ {s:15s} → {result[s].get('domaine')}")
        else:
            print(f"   ❌ Section manquante : {s}")
            ok = False

    if not ok:
        print("\n❌ Structure invalide.")
        return

    # --- 4. Sauvegarde JSON ---
    print("\n💾 [4/4] Sauvegarde du résultat...")
    out_dir = Path("outputs")
    out_dir.mkdir(exist_ok=True)
    out_file = out_dir / "agent1_test_output.json"
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)
    print(f"   ✅ Sauvegardé : {out_file}")

    # --- Résumé ---
    print("\n" + "=" * 70)
    print("✅ TEST TERMINÉ AVEC SUCCÈS")
    print("=" * 70)
    print(f"📊 Résumé:")
    print(f"   • Inscription   : {len(result['inscription']['questions'])} questions")
    print(f"   • Test AVANT    : {len(result['test_avant']['questions'])} questions")
    print(f"   • Test APRÈS    : {len(result['test_apres']['questions'])} questions")
    print(f"   • Satisfaction  : {len(result['satisfaction']['questions'])} questions")
    print(f"   • Durée totale  : {elapsed}s")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())