"""
Test Agent M3 COMPLET — OffreOrchestrator
==========================================
Teste la génération d'une offre complète (technique + financière + HITL).

Usage :
    python scripts/test_agent_m3_complet.py
"""

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

from app.orchestrator.offre_orchestrator import (
    OffreOrchestrator,
    get_offre_orchestrator,
)


# ============================================================
# DONNÉES DE TEST
# ============================================================

TDR_DATA = {
    "id": 1,
    "titre": "Introduction à l'IA générative",
    "domaine": "IA",
    "objectifs": [
        "Comprendre les concepts de l'IA générative",
        "Maîtriser le Prompt Engineering",
        "Créer des applications avec LLM",
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
}

OPTIONS = {
    "nb_participants": 20,
    "type_formateur": "senior",
    "type_salle": "standard",
    "tva_applicable": True,
    "inclure_logistique": True,
    "inclure_administration": True,
}


# ============================================================
# TEST
# ============================================================

async def main():
    print("=" * 70)
    print("🧪 TEST AGENT M3 COMPLET — OffreOrchestrator")
    print("=" * 70)

    # ── 1. Init orchestrateur ──
    print("\n🔧 [1/5] Initialisation de l'orchestrateur...")
    try:
        orch = get_offre_orchestrator()
        print("   ✅ Orchestrateur prêt")
    except Exception as e:
        print(f"   ❌ Échec init : {e}")
        return

    # ── 2. Génération complète ──
    print("\n🚀 [2/5] Génération de l'offre complète...")
    print(f"   📋 TDR : {TDR_DATA.get('titre')}")
    print(f"   🏢 Client : {SESSION_INFO.get('client')}")
    print(f"   👥 Participants : {OPTIONS.get('nb_participants')}")

    try:
        result = await orch.generate_complete(
            tdr_data=TDR_DATA,
            session_info=SESSION_INFO,
            options=OPTIONS,
        )
        print(f"   ✅ Offre complète générée")
    except Exception as e:
        print(f"   ❌ Échec : {e}")
        import traceback
        traceback.print_exc()
        return

    # ── 3. Vérification ──
    print("\n🔍 [3/5] Vérification de la structure...")
    required_keys = [
        "offre_technique", "offre_financiere",
        "resume_financier", "reviews_individuels",
        "_review_id", "_review_status",
    ]
    ok = True
    for key in required_keys:
        if key in result:
            print(f"   ✅ {key}")
        else:
            print(f"   ❌ Manquant : {key}")
            ok = False

    # ── 4. Résumé ──
    print("\n📊 [4/5] Résumé complet :")

    offre_tech = result.get("offre_technique", {})
    offre_fin = result.get("offre_financiere", {})
    resume = result.get("resume_financier", {})

    print(f"\n📝 OFFRE TECHNIQUE :")
    print(f"   • Référence : {offre_tech.get('reference')}")
    print(f"   • Titre     : {offre_tech.get('titre_offre')}")
    print(f"   • Modules   : {len(offre_tech.get('programme', {}).get('modules', []))}")
    print(f"   • Source    : {offre_tech.get('metadata', {}).get('source')}")

    print(f"\n💰 OFFRE FINANCIÈRE :")
    print(f"   • Référence : {offre_fin.get('reference')}")
    print(f"   • Sous-total HT : {resume.get('sous_total_ht', 0):>12,} MGA")
    print(f"   • Total TTC     : {resume.get('total_ttc', 0):>12,} MGA")
    print(f"   • NET À PAYER   : {resume.get('net_a_payer', 0):>12,} MGA")
    print(f"   • Source        : {offre_fin.get('metadata', {}).get('source')}")

    print(f"\n🔗 REVIEWS HITL :")
    reviews = result.get("reviews_individuels", {})
    print(f"   • Review TECH individuel   : {reviews.get('technique')}")
    print(f"   • Review FIN individuel    : {reviews.get('financiere')}")
    print(f"   • Review GLOBAL (à valider): {result.get('_review_id')}")
    print(f"   • Statut global            : {result.get('_review_status')}")

    print(f"\n⏱️  DURÉES :")
    print(f"   • Offre technique  : {offre_tech.get('metadata', {}).get('duration_seconds')}s")
    print(f"   • Offre financière : {offre_fin.get('metadata', {}).get('duration_seconds')}s")

    # ── 5. Sauvegarde ──
    out = Path("outputs")
    out.mkdir(exist_ok=True)
    f = out / "agent_m3_complet_output.json"
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