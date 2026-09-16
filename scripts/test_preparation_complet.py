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

from app.orchestrator.preparation_orchestrator import (
    PreparationOrchestrator,
    get_preparation_orchestrator,
)


# ============================================================
# DONNÉES DE TEST
# ============================================================

OFFRE_DATA = {
    "reference": "ALT-OFF-TECH-2026-0001",
    "titre": "Introduction à l'IA générative",
    "duree_jours": 2,
    "modules": [
        {"titre": "Fondements de l'IA générative", "duree": "3h"},
        {"titre": "Prompt Engineering avancé", "duree": "4h"},
        {"titre": "Développement d'applications LLM", "duree": "4h"},
        {"titre": "Projet de synthèse", "duree": "5h"},
    ],
}

PROJET_INFO = {
    "id": 1,
    "offre_id": 1,
    "marche_id": 1,
    "client": "Ministère de l'Éducation Nationale",
    "client_id": 1,
    "nb_participants": 20,
}

RESSOURCES = {
    "formateur": {
        "nom": "M. RANAIVOSOA S.",
        "tarif_journalier": 500_000,
        "specialite": "IA & Prompt Engineering",
    },
    "salle": {
        "nom": "Salle A — ALTIORA Prest",
        "tarif_journalier": 200_000,
        "adresse": "Antananarivo",
    },
}

OPTIONS = {
    "date_debut": "2026-10-15",
    "date_fin": "2026-10-16",
    "inclure_logistique": True,
    "inclure_administration": True,
}


# ============================================================
# TEST
# ============================================================

async def main():
    print("=" * 70)
    print("🧪 TEST PRÉPARATION COMPLET — PreparationOrchestrator")
    print("=" * 70)

    # ── 1. Init ──
    print("\n🔧 [1/4] Initialisation de l'orchestrateur...")
    try:
        orch = get_preparation_orchestrator()
        print("   ✅ Orchestrateur prêt")
    except Exception as e:
        print(f"   ❌ Échec init : {e}")
        return

    # ── 2. Génération ──
    print("\n🚀 [2/4] Génération de la préparation complète...")
    print(f"   📋 Offre : {OFFRE_DATA.get('reference')}")
    print(f"   🏢 Client : {PROJET_INFO.get('client')}")
    print(f"   👥 Participants : {PROJET_INFO.get('nb_participants')}")

    try:
        result = await orch.generate_complete(
            offre_data=OFFRE_DATA,
            projet_info=PROJET_INFO,
            ressources=RESSOURCES,
            options=OPTIONS,
        )
        print("   ✅ Préparation générée")
    except Exception as e:
        print(f"   ❌ Échec : {e}")
        import traceback
        traceback.print_exc()
        return

    # ── 3. Vérification ──
    print("\n🔍 [3/4] Vérification de la structure...")
    required = ["budget", "edt", "_review_id", "_review_status"]
    ok = True
    for key in required:
        if key in result:
            print(f"   ✅ {key}")
        else:
            print(f"   ❌ Manquant : {key}")
            ok = False

    # ── 4. Résumé ──
    print("\n📊 [4/4] Résumé complet :")

    budget = result.get("budget", {})
    edt = result.get("edt", {})

    print(f"\n💰 BUDGET :")
    print(f"   • Formateur      : {budget.get('cout_formateur', 0):>12,} MGA")
    print(f"   • Salle          : {budget.get('cout_salle', 0):>12,} MGA")
    print(f"   • Supports       : {budget.get('cout_supports', 0):>12,} MGA")
    print(f"   • Logistique     : {budget.get('cout_logistique', 0):>12,} MGA")
    print(f"   • Administration : {budget.get('cout_administration', 0):>12,} MGA")
    print(f"   {'─' * 35}")
    print(f"   • TOTAL          : {budget.get('cout_total', 0):>12,} MGA")

    print(f"\n📅 EDT :")
    print(f"   • Formation      : {edt.get('titre_formation')}")
    print(f"   • Durée          : {edt.get('duree_totale_jours')} jour(s)")
    print(f"   • Sessions       : {sum(len(j.get('sessions', [])) for j in edt.get('jours', []))}")
    print(f"   • Source         : {edt.get('metadata', {}).get('source')}")

    print(f"\n🔗 HITL :")
    print(f"   • Review ID      : {result.get('_review_id')}")
    print(f"   • Statut         : {result.get('_review_status')}")

    # ── Sauvegarde ──
    out = Path("outputs")
    out.mkdir(exist_ok=True)
    f = out / "preparation_complet_output.json"
    with open(f, "w", encoding="utf-8") as fp:
        json.dump(result, fp, indent=2, ensure_ascii=False)
    print(f"\n💾 Sauvegardé : {f}")

    print("\n" + "=" * 70)
    if ok:
        print("✅ TEST TERMINÉ AVEC SUCCÈS")
        print(f"\n🎯 Action suivante :")
        print(f"   Approuver le review : POST /ia/formations/reviews/"
              f"{result.get('_review_id')}/approve")
    else:
        print("⚠️  TEST TERMINÉ AVEC AVERTISSEMENTS")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())