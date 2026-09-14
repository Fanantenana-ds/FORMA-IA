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

from app.services.formations.satisfaction_analyzer_service import (
    SatisfactionAnalyzerService,
)


SESSION = {
    "id": 1,
    "titre": "Introduction à l'IA",
    "domaine": "IA",
    "formateur": "Rakoto",
}


# 6 réponses représentatives
RESPONSES = [
    {
        "note_globale": 5, "note_formateur": 5, "note_contenu": 4,
        "note_supports": 4, "note_organisation": 5,
        "points_forts": "Formateur excellent, très pédagogue. Beaucoup d'exemples concrets.",
        "points_faibles": "",
        "suggestions": "Ajouter plus d'exercices pratiques sur les cas métier.",
        "recommandation": "Oui",
    },
    {
        "note_globale": 4, "note_formateur": 5, "note_contenu": 4,
        "note_supports": 3, "note_organisation": 4,
        "points_forts": "Contenu structuré et progressif.",
        "points_faibles": "Les supports PDF sont un peu denses.",
        "suggestions": "Alléger les slides et ajouter des schémas.",
        "recommandation": "Oui",
    },
    {
        "note_globale": 5, "note_formateur": 5, "note_contenu": 5,
        "note_supports": 4, "note_organisation": 5,
        "points_forts": "Formation très complète, rythme adapté.",
        "points_faibles": "",
        "suggestions": "",
        "recommandation": "Oui",
    },
    {
        "note_globale": 3, "note_formateur": 4, "note_contenu": 3,
        "note_supports": 3, "note_organisation": 3,
        "points_forts": "Bonne ambiance, formateur disponible.",
        "points_faibles": "Trop rapide sur la fin, manque de temps pour les questions.",
        "suggestions": "Prévoir 30 min de plus pour les Q&A.",
        "recommandation": "Peut-être",
    },
    {
        "note_globale": 4, "note_formateur": 5, "note_contenu": 4,
        "note_supports": 4, "note_organisation": 4,
        "points_forts": "Formateur passionné, cas pratiques pertinents.",
        "points_faibles": "",
        "suggestions": "Proposer un module de suivi à distance.",
        "recommandation": "Oui",
    },
    {
        "note_globale": 5, "note_formateur": 5, "note_contenu": 5,
        "note_supports": 5, "note_organisation": 5,
        "points_forts": "Tout était parfait. Formation très professionnelle.",
        "points_faibles": "",
        "suggestions": "Reconduire la formation chaque année.",
        "recommandation": "Oui",
    },
]


async def main():
    print("=" * 70)
    print("🧪 TEST AGENT 3 — SatisfactionAnalyzerService")
    print("=" * 70)

    service = SatisfactionAnalyzerService()

    result = await service.analyze(SESSION, RESPONSES)

    print(f"\n📊 Source           : {result['metadata']['source']}")
    print(f"⏱️  Durée            : {result['metadata']['duration_seconds']}s")
    print(f"📈 Nombre réponses  : {result['statistiques']['nb_reponses']}")

    print("\n⭐ NOTES MOYENNES :")
    for k, v in result["statistiques"]["notes"].items():
        label = k.replace("note_", "").capitalize()
        print(f"   • {label:15s} : {v}/5")

    print(f"\n📢 Taux de recommandation : {result['statistiques']['taux_recommandation']}")
    print(f"   • Recommandent    : {result['statistiques']['nb_recommandent']}")
    print(f"   • Neutres         : {result['statistiques']['nb_neutres']}")
    print(f"   • Déconseillent   : {result['statistiques']['nb_deconseillent']}")

    print(f"\n✅ Points forts ({len(result['points_forts'])}) :")
    for i, p in enumerate(result["points_forts"], 1):
        print(f"   {i}. {p}")

    print(f"\n⚠️  Axes d'amélioration ({len(result['axes_amelioration'])}) :")
    for i, a in enumerate(result["axes_amelioration"], 1):
        print(f"   {i}. {a}")

    print(f"\n🔁 Thèmes récurrents ({len(result['themes_recurrents'])}) :")
    for t in result["themes_recurrents"]:
        print(f"   • {t['theme']} (fréquence: {t['frequence']}, sentiment: {t['sentiment']})")

    print(f"\n💡 Recommandations ({len(result['recommandations'])}) :")
    for i, r in enumerate(result["recommandations"], 1):
        print(f"   {i}. {r}")

    print(f"\n📝 Interprétation :\n   {result['interpretation']}")

    out = Path("outputs"); out.mkdir(exist_ok=True)
    f = out / "agent3_test_output.json"
    with open(f, "w", encoding="utf-8") as fp:
        json.dump(result, fp, indent=2, ensure_ascii=False)
    print(f"\n💾 Sauvegardé : {f}")

    print("\n" + "=" * 70)
    print("✅ TEST TERMINÉ")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())