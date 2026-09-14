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

from app.services.formations.presence_analyzer_service import (
    PresenceAnalyzerService,
)


# ============================================================
# DONNÉES DE TEST
# ============================================================
SESSION = {
    "id": 1,
    "titre": "Introduction à l'IA",
    "date_debut": "2026-10-15",
    "date_fin": "2026-10-16",
    "lieu": "Antananarivo",
}

PARTICIPANTS = [
    {"id": 1, "nom": "Jean Dupont", "email": "jean@example.com"},
    {"id": 2, "nom": "Marie Rasoa", "email": "marie@example.com"},
    {"id": 3, "nom": "Paul Andry", "email": "paul@example.com"},
    {"id": 4, "nom": "Sophie R.", "email": "sophie@example.com"},
]

# 2 séances : 2026-10-15 et 2026-10-16
PRESENCES = [
    # ── Séance 1 (15 oct) ──
    {"participant_id": 1, "date": "2026-10-15", "heure": "08:30:00", "present": True, "methode": "qr_code"},
    {"participant_id": 2, "date": "2026-10-15", "heure": "08:35:00", "present": True, "methode": "qr_code"},
    {"participant_id": 3, "date": "2026-10-15", "heure": "08:45:00", "present": True, "methode": "qr_code"},
    {"participant_id": 4, "date": "2026-10-15", "heure": "09:00:00", "present": True, "methode": "form"},

    # ── Séance 2 (16 oct) ──
    {"participant_id": 1, "date": "2026-10-16", "heure": "08:30:00", "present": True, "methode": "qr_code"},
    {"participant_id": 2, "date": "2026-10-16", "heure": "08:35:00", "present": True, "methode": "qr_code"},
    {"participant_id": 3, "date": "2026-10-16", "heure": "08:45:00", "present": False, "methode": "qr_code"},  # Absent
    # Sophie : pas de scan séance 2 (absente)
    {"participant_id": 4, "date": "2026-10-16", "heure": "09:00:00", "present": False, "methode": "form"},

    # ── Anomalies volontaires ──
    # Doublon (Jean, 15 oct, 08:30)
    {"participant_id": 1, "date": "2026-10-15", "heure": "08:30:00", "present": True, "methode": "qr_code"},
    # Participant inconnu (ID=999)
    {"participant_id": 999, "date": "2026-10-16", "heure": "08:30:00", "present": True, "methode": "qr_code"},
    # Présence hors plage (05:30)
    {"participant_id": 2, "date": "2026-10-16", "heure": "05:30:00", "present": True, "methode": "qr_code"},
]


async def main():
    print("=" * 70)
    print("🧪 TEST AGENT 4 — PresenceAnalyzerService (Python pur)")
    print("=" * 70)

    service = PresenceAnalyzerService()

    result = service.analyze(SESSION, PARTICIPANTS, PRESENCES)

    print(f"\n📊 Méthode           : {result['metadata']['methode']}")
    print(f"⏱️  Durée            : {result['metadata']['duration_seconds']}s")
    print(f"\n📝 Résumé :\n   {result['resume']}")

    print(f"\n📈 STATS GLOBALES :")
    s = result["statistiques"]
    print(f"   • Participants    : {s['total_participants']}")
    print(f"   • Séances         : {s['total_seances']}")
    print(f"   • Taux global     : {s['taux_presence_global']}")
    print(f"   • Présents moyen  : {s['nb_presents_moyen']}/séance")
    print(f"   • Absents total   : {s['nb_absents_total']}")

    print(f"\n👥 STATS PAR PARTICIPANT :")
    for p in result["participants"]:
        flag = "✅" if p["eligible_attestation"] else "❌"
        print(f"   {flag} {p['nom']:15s} : {p['taux_presence']:>6s} "
              f"({p['nb_presences']}/{p['nb_seances']})")

    print(f"\n🔍 ANOMALIES ({len(result['anomalies'])}) :")
    for a in result["anomalies"]:
        icon = {"info": "ℹ️", "warning": "⚠️", "error": "❌"}[a["severity"]]
        print(f"   {icon} [{a['type']}] {a['message']}")

    print(f"\n✅ ÉLIGIBLES ATTESTATION ({len(result['eligibles_attestation'])}) :")
    for nom in result["eligibles_attestation"]:
        print(f"   • {nom}")

    print(f"\n❌ NON ÉLIGIBLES ({len(result['non_eligibles_attestation'])}) :")
    for nom in result["non_eligibles_attestation"]:
        print(f"   • {nom}")

    print(f"\n💡 RECOMMANDATIONS ({len(result['recommandations'])}) :")
    for i, r in enumerate(result["recommandations"], 1):
        print(f"   {i}. {r}")

    out = Path("outputs"); out.mkdir(exist_ok=True)
    f = out / "agent4_test_output.json"
    with open(f, "w", encoding="utf-8") as fp:
        json.dump(result, fp, indent=2, ensure_ascii=False)
    print(f"\n💾 Sauvegardé : {f}")

    print("\n" + "=" * 70)
    print("✅ TEST TERMINÉ")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())