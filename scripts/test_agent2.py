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

from app.services.formations.level_analyzer_service import LevelAnalyzerService


SESSION = {
    "id": 1,
    "titre": "Introduction à l'IA",
    "domaine": "IA",
    "niveau_cible": "Intermédiaire",
}

# Corrigé : 5 questions (simplifié)
CORRIGE = {"av_01": "A", "av_02": "B", "av_03": "C", "av_04": "B", "av_05": "B"}

# Participants avec réponses
def mk(avant, apres):
    return avant, apres

PARTICIPANTS = [
    {
        "id": 1, "nom": "Jean Dupont",
        "reponses_avant": {"av_01": "A", "av_02": "B", "av_03": "A", "av_04": "B", "av_05": "A"},
        "reponses_apres": {"ap_01": "A", "ap_02": "B", "ap_03": "C", "ap_04": "B", "ap_05": "B"},
    },
    {
        "id": 2, "nom": "Marie Rasoa",
        "reponses_avant": {"av_01": "A", "av_02": "A", "av_03": "A", "av_04": "B", "av_05": "A"},
        "reponses_apres": {"ap_01": "A", "ap_02": "B", "ap_03": "C", "ap_04": "B", "ap_05": "B"},
    },
    {
        "id": 3, "nom": "Paul Andry",
        "reponses_avant": {"av_01": "A", "av_02": "A", "av_03": "A", "av_04": "A", "av_05": "A"},
        "reponses_apres": {"ap_01": "A", "ap_02": "B", "ap_03": "A", "ap_04": "B", "ap_05": "A"},
    },
    {
        "id": 4, "nom": "Sophie R.",
        "reponses_avant": {"av_01": "A", "av_02": "B", "av_03": "C", "av_04": "B", "av_05": "B"},
        "reponses_apres": {"ap_01": "A", "ap_02": "B", "ap_03": "C", "ap_04": "B", "ap_05": "B"},
    },
]


async def main():
    print("=" * 70)
    print("🧪 TEST AGENT 2 — LevelAnalyzerService")
    print("=" * 70)

    service = LevelAnalyzerService()

    result = await service.analyze(SESSION, PARTICIPANTS, CORRIGE)

    print(f"\n📊 Source       : {result['metadata']['source']}")
    print(f"⏱️  Durée        : {result['metadata']['duration_seconds']}s")
    print(f"\n📈 Score AVANT  : {result['statistiques']['score_moyen_avant']}/100")
    print(f"📈 Score APRÈS  : {result['statistiques']['score_moyen_apres']}/100")
    print(f"📈 Progression  : +{result['statistiques']['progression_absolue']} "
          f"({result['statistiques']['progression_relative']})")
    print(f"\n🎯 Distribution AVANT : {result['distribution_avant']}")
    print(f"🎯 Distribution APRÈS : {result['distribution_apres']}")
    print(f"\n🏆 Meilleure progression : {result['cas_remarquables']['meilleure_progression']}")
    print(f"\n💡 Recommandations ({len(result['recommandations'])}) :")
    for i, r in enumerate(result["recommandations"], 1):
        print(f"   {i}. {r}")

    out = Path("outputs"); out.mkdir(exist_ok=True)
    f = out / "agent2_test_output.json"
    with open(f, "w", encoding="utf-8") as fp:
        json.dump(result, fp, indent=2, ensure_ascii=False)
    print(f"\n💾 Sauvegardé : {f}")

    print("\n" + "=" * 70)
    print("✅ TEST TERMINÉ")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())