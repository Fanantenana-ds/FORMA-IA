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

from app.services.preparation import EDTGeneratorService


# ============================================================
# DONNÉES DE TEST
# ============================================================

TITRE = "Introduction à l'IA générative"

MODULES = [
    {"titre": "Fondements de l'IA générative", "duree": "3h"},
    {"titre": "Prompt Engineering avancé", "duree": "4h"},
    {"titre": "Développement d'applications LLM", "duree": "4h"},
    {"titre": "Projet de synthèse", "duree": "5h"},
]

DATES = ["2026-10-15", "2026-10-16"]

FORMATEUR = {
    "nom": "M. RANAIVOSOA S.",
    "specialite": "IA & Prompt Engineering",
}

SALLE = {
    "nom": "Salle A — ALTIORA Prest",
    "adresse": "Antananarivo",
}


# ============================================================
# TEST
# ============================================================

async def main():
    print("=" * 70)
    print("🧪 TEST PRÉPARATION — EDTGeneratorService")
    print("=" * 70)

    # ── 1. Init ──
    print("\n🔧 [1/3] Initialisation du service...")
    try:
        service = EDTGeneratorService()
        print("   ✅ Service initialisé")
    except Exception as e:
        print(f"   ❌ Échec init : {e}")
        return

    # ── 2. Génération ──
    print("\n📅 [2/3] Génération de l'emploi du temps...")
    try:
        result = await service.generate(
            titre_formation=TITRE,
            modules=MODULES,
            dates=DATES,
            formateur=FORMATEUR,
            salle=SALLE,
        )
        print("   ✅ EDT généré")
    except Exception as e:
        print(f"   ❌ Échec : {e}")
        import traceback
        traceback.print_exc()
        return

    # ── 3. Résumé ──
    print("\n📊 [3/3] Résumé de l'EDT :")
    print(f"   📄 Formation  : {result.get('titre_formation')}")
    print(f"   📅 Durée      : {result.get('duree_totale_jours')} jour(s)")
    print(f"   📚 Modules    : {result.get('nombre_modules')}")
    print(f"   🤖 Source     : {result.get('metadata', {}).get('source')}")
    print(f"   ⏱️  Durée      : {result.get('metadata', {}).get('duration_seconds')}s")

    # Formateur + salle
    formateur = result.get("formateur", {})
    salle = result.get("salle", {})
    print(f"   👤 Formateur  : {formateur.get('nom', 'N/A')}")
    print(f"   🏛️  Salle      : {salle.get('nom', 'N/A')}")

    # Jours
    jours = result.get("jours", [])
    print(f"\n📅 JOURS ({len(jours)}) :")
    for j in jours:
        print(f"\n   ── Jour {j.get('numero')} — {j.get('date')} ──")
        for s in j.get("sessions", []):
            print(f"      • {s.get('heure_debut')}-{s.get('heure_fin')} : "
                  f"{s.get('module', '')[:40]} [{s.get('type')}]")
        pauses = j.get("pauses", [])
        if pauses:
            print(f"      Pauses : {', '.join(p.get('type', '') for p in pauses)}")

    # Résumé
    resume = result.get("resume_hebdomadaire", {})
    if resume:
        print(f"\n📊 RÉSUMÉ :")
        print(f"   • Total heures   : {resume.get('total_heures')}h")
        print(f"   • Total sessions : {resume.get('total_sessions')}")
        print(f"   • Modules        : {resume.get('modules_couverts')}")
        print(f"   • Charge/jour    : {resume.get('charge_journaliere_moyenne')}h")

    # ── Sauvegarde ──
    out = Path("outputs")
    out.mkdir(exist_ok=True)
    f = out / "preparation_edt_output.json"
    with open(f, "w", encoding="utf-8") as fp:
        json.dump(result, fp, indent=2, ensure_ascii=False)
    print(f"\n💾 Sauvegardé : {f}")

    print("\n" + "=" * 70)
    print("✅ TEST TERMINÉ")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())