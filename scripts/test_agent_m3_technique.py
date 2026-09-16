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

from app.services.offres.offre_technique_service import (
    OffreTechniqueGeneratorService,
)


# ============================================================
# DONNÉES DE TEST
# ============================================================

TDR_DATA = {
    "id": 1,
    "titre": "Introduction à l'IA",
    "domaine": "IA",
    "objectifs": [
        "Comprendre les concepts fondamentaux de l'IA",
        "Pratiquer avec des cas concrets",
        "Identifier les cas d'usage métier",
    ],
    "public_cible": "Développeurs juniors du Ministère de l'Éducation",
    "duree_jours": 2,
    "lieu": "Antananarivo",
}

SESSION_INFO = {
    "id": 1,
    "client": "Ministère de l'Éducation Nationale",
    "client_id": 1,
    "formateur": "M. RANAIVOSOA S.",
    "nb_participants": 20,
}


# ============================================================
# TEST
# ============================================================

async def main():
    print("=" * 70)
    print("🧪 TEST AGENT M3-1 — OffreTechniqueGeneratorService")
    print("=" * 70)

    # ── 1. Init service ──
    print("\n🔧 [1/4] Initialisation du service...")
    try:
        service = OffreTechniqueGeneratorService()
        print("   ✅ Service initialisé")
    except Exception as e:
        print(f"   ❌ Échec init : {e}")
        return

    # ── 2. Appel LLM ──
    print("\n🚀 [2/4] Génération de l'offre technique (LLM)...")
    try:
        result = await service.generate(
            tdr_data=TDR_DATA,
            session_info=SESSION_INFO,
        )
        print(f"   ✅ Offre générée")
    except Exception as e:
        print(f"   ❌ Échec génération : {e}")
        import traceback
        traceback.print_exc()
        return

    # ── 3. Vérification ──
    print("\n🔍 [3/4] Vérification de la structure...")
    required_keys = [
        "titre_offre", "reference", "date_emission",
        "presentation_structure", "comprehension_besoin",
        "approche_methodologique", "programme",
        "ressources", "planning", "garanties",
        "points_forts", "conclusion",
        "_review_id",
    ]
    ok = True
    for key in required_keys:
        if key in result:
            print(f"   ✅ {key}")
        else:
            print(f"   ❌ Manquant : {key}")
            ok = False

    # ── 4. Résumé ──
    print("\n📊 [4/4] Résumé :")
    print(f"   📄 Titre     : {result.get('titre_offre')}")
    print(f"   🔖 Référence : {result.get('reference')}")
    print(f"   📅 Date      : {result.get('date_emission')}")
    print(f"   🤖 Source    : {result.get('metadata', {}).get('source')}")
    print(f"   ⏱️  Durée     : {result.get('metadata', {}).get('duration_seconds')}s")
    print(f"   ⏳ Review    : {result.get('_review_id')}")

    # Modules
    modules = result.get("programme", {}).get("modules", [])
    print(f"   📚 Modules   : {len(modules)}")
    for m in modules[:3]:
        print(f"      • Module {m.get('numero')} : {m.get('titre')} ({m.get('duree')})")

    # ── 5. Sauvegarde ──
    out = Path("outputs")
    out.mkdir(exist_ok=True)
    f = out / "agent_m3_technique_output.json"
    with open(f, "w", encoding="utf-8") as fp:
        json.dump(result, fp, indent=2, ensure_ascii=False)
    print(f"\n💾 Sauvegardé : {f}")

    print("\n" + "=" * 70)
    if ok:
        print("✅ TEST TERMINÉ AVEC SUCCÈS")
    else:
        print("⚠️  TEST TERMINÉ AVEC AVERTISSEMENTS")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())