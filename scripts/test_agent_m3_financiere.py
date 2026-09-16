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

from app.services.offres.offre_financiere_service import (
    OffreFinanciereGeneratorService,
)


# ============================================================
# DONNÉES DE TEST
# ============================================================

OFFRE_TECHNIQUE = {
    "success": True,
    "titre_offre": "Offre technique — Introduction à l'IA",
    "reference": "ALT-OFF-TECH-2026-0001",
    "date_emission": "2026-09-16",
    "programme": {
        "duree_totale": "2 jours (14 heures)",
        "modules": [
            {"numero": 1, "titre": "Introduction à l'IA", "duree": "3h"},
            {"numero": 2, "titre": "Apprentissage automatique", "duree": "3h"},
            {"numero": 3, "titre": "LLM et génération", "duree": "3h"},
            {"numero": 4, "titre": "Projet pratique", "duree": "3h"},
        ],
    },
    "ressources": {
        "formateur": {
            "nom": "M. RANAIVOSOA S.",
            "profil": "Expert IA",
        },
    },
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
    print("🧪 TEST AGENT M3-2 — OffreFinanciereGeneratorService")
    print("=" * 70)

    # ── 1. Init ──
    print("\n🔧 [1/4] Initialisation du service...")
    try:
        service = OffreFinanciereGeneratorService()
        print("   ✅ Service initialisé")
    except Exception as e:
        print(f"   ❌ Échec init : {e}")
        return

    # ── 2. Génération ──
    print("\n🚀 [2/4] Génération de l'offre financière...")
    try:
        result = await service.generate(
            offre_technique=OFFRE_TECHNIQUE,
            options=OPTIONS,
        )
        print(f"   ✅ Offre financière générée")
    except Exception as e:
        print(f"   ❌ Échec : {e}")
        import traceback
        traceback.print_exc()
        return

    # ── 3. Vérification ──
    print("\n🔍 [3/4] Vérification de la structure...")
    required_keys = [
        "titre_offre", "reference", "date_emission",
        "devise", "details_couts", "recapitulatif",
        "echeancier", "conditions_financieres",
        "conclusion", "_review_id",
    ]
    ok = True
    for key in required_keys:
        if key in result:
            print(f"   ✅ {key}")
        else:
            print(f"   ❌ Manquant : {key}")
            ok = False

    # ── 4. Résumé ──
    print("\n📊 [4/4] Résumé financier :")
    print(f"   📄 Titre     : {result.get('titre_offre')}")
    print(f"   🔖 Référence : {result.get('reference')}")
    print(f"   💰 Devise    : {result.get('devise')}")
    print(f"   🤖 Source    : {result.get('metadata', {}).get('source')}")
    print(f"   ⏱️  Durée     : {result.get('metadata', {}).get('duration_seconds')}s")
    print(f"   ⏳ Review    : {result.get('_review_id')}")

    # Détails coûts
    details = result.get("details_couts", {})
    print(f"\n💵 DÉTAILS DES COÛTS :")
    for name, cout in details.items():
        if isinstance(cout, dict) and "sous_total" in cout:
            print(f"   • {name:25s} : {cout['sous_total']:>12,} MGA")
        elif isinstance(cout, dict) and "montant" in cout:
            print(f"   • {name:25s} : {cout['montant']:>12,} MGA")

    # Récapitulatif
    recap = result.get("recapitulatif", {})
    print(f"\n💰 RÉCAPITULATIF :")
    print(f"   • Sous-total HT : {recap.get('sous_total_ht', 0):>12,} MGA")
    tva = recap.get("tva", {})
    print(f"   • TVA ({tva.get('taux', 0)}%)    : {tva.get('montant', 0):>12,} MGA")
    print(f"   • Total TTC     : {recap.get('total_ttc', 0):>12,} MGA")

    remises = recap.get("remises", [])
    for r in remises:
        print(f"   • Remise ({r.get('pourcentage')}%) : -{r.get('montant', 0):>11,} MGA")

    print(f"   • NET À PAYER   : {recap.get('net_a_payer', 0):>12,} MGA")

    # Échéancier
    echeances = result.get("echeancier", [])
    print(f"\n📅 ÉCHÉANCIER ({len(echeances)}) :")
    for e in echeances:
        print(f"   • {e.get('ordre')}. {e.get('libelle'):30s} "
              f"{e.get('pourcentage'):>3}% — {e.get('montant'):>12,} MGA ({e.get('delai')})")

    # ── 5. Sauvegarde ──
    out = Path("outputs")
    out.mkdir(exist_ok=True)
    f = out / "agent_m3_financiere_output.json"
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