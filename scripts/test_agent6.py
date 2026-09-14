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

from app.services.formations.report_generator_service import (
    ReportGeneratorService,
)


# ============================================================
# DONNÉES AGRÉGÉES DE SESSION (comme si le Backend les avait fournies)
# ============================================================
SESSION_DATA = {
    "id": 1,
    "titre": "Introduction à l'IA",
    "domaine": "IA",
    "niveau_cible": "Intermédiaire",
    "date_debut": "2026-10-15",
    "date_fin": "2026-10-16",
    "lieu": "Antananarivo",
    "formateur": "Rakoto",
    "duree_jours": 2,
    "public_cible": "Ministère de l'Éducation",
    # Stats
    "total_inscrits": 20,
    "total_presents": 18,
    "taux_presence": "90%",
    "entreprises": ["Ministère de l'Éducation", "ONG Tsinjo", "Entreprise X"],
    # Niveaux
    "niveaux_avant": {"debutants": "60%", "intermediaires": "30%", "avances": "10%"},
    "niveaux_apres": {"debutants": "10%", "intermediaires": "60%", "avances": "30%"},
    "progression": "+40%",
    # Satisfaction
    "note_globale": "4.2/5",
    "note_formateur": "4.5/5",
    "note_contenu": "4.0/5",
    "note_supports": "4.0/5",
    "note_organisation": "4.3/5",
    "points_forts": [
        "Contenu clair et bien structuré",
        "Formateur pédagogue et disponible",
        "Exercices pratiques pertinents",
    ],
    "axes_amelioration": [
        "Ajouter plus de cas d'usage métier",
        "Prévoir plus de temps pour les questions",
    ],
    "taux_recommandation": "90%",
}


async def main():
    print("=" * 70)
    print("🧪 TEST AGENT 6 — ReportGeneratorService")
    print("=" * 70)

    service = ReportGeneratorService()

    print("\n🚀 Génération du rapport final...")
    result = await service.generate(SESSION_DATA)

    print(f"\n📄 Titre    : {result.get('titre_rapport')}")
    print(f"📊 Source   : {result['metadata']['source']}")
    print(f"⏱️  Durée    : {result['metadata']['duration_seconds']}s")
    print(f"💡 Recos    : {len(result.get('recommandations', []))}")
    print(f"\n📝 Résumé exécutif :\n{result.get('resume_executif')}")

    print(f"\n💡 Recommandations :")
    for i, r in enumerate(result["recommandations"], 1):
        print(f"   {i}. {r}")

    print(f"\n📌 Conclusion :\n   {result.get('conclusion')}")

    # Sauvegarde
    out = Path("outputs")
    out.mkdir(exist_ok=True)
    f = out / "agent6_test_output.json"
    with open(f, "w", encoding="utf-8") as fp:
        json.dump(result, fp, indent=2, ensure_ascii=False)
    print(f"\n💾 Sauvegardé : {f}")

    print("\n" + "=" * 70)
    print("✅ TEST TERMINÉ")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())