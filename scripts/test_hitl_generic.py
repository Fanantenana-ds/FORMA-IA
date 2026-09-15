"""Test HITL Générique — FORMA-IA."""

import sys
from pathlib import Path

from dotenv import load_dotenv
load_dotenv()
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
    datefmt="%H:%M:%S",
)

from app.services.hitl import (
    create_review,
    list_pending,
    get_review,
    approve_review,
    reject_review,
    get_stats,
)


def main():
    print("=" * 70)
    print("🧪 TEST HITL GÉNÉRIQUE — FORMA-IA")
    print("=" * 70)

    # 1. Créer un review (simulation M5)
    print("\n[1/5] create_review() — Agent 1 (forms)")
    review_id = create_review(
        agent_id="agent_1_forms",
        data={"inscription": {"questions": []}, "test_avant": {"questions": []}},
        summary="Test générique — 2 formulaires",
        criticity="critical",
    )
    print(f"   ✅ Review créé : {review_id}")

    # 2. Créer un review (simulation M3)
    print("\n[2/5] create_review() — Agent M3 (offre technique)")
    review_id_m3 = create_review(
        agent_id="agent_m3_technique",
        data={"trame_technique": "..."},
        summary="Offre technique — Test",
    )
    print(f"   ✅ Review créé : {review_id_m3}")

    # 3. Lister les pending
    print("\n[3/5] list_pending()")
    pendings = list_pending()
    print(f"   ✅ Total en attente : {len(pendings)}")
    for p in pendings[:3]:
        print(f"      • {p['review_id']} [{p['criticity']}] {p['agent_id']}")

    # 4. Approuver
    print(f"\n[4/5] approve_review() — {review_id}")
    approved = approve_review(review_id, reviewer_note="Validé par test")
    if approved:
        print(f"   ✅ Status : {approved['status']}")

    # 5. Stats
    print("\n[5/5] get_stats()")
    stats = get_stats()
    print(f"   ✅ Total    : {stats['total']}")
    print(f"   ✅ Pending  : {stats['pending']}")
    print(f"   ✅ Approved : {stats['approved']}")
    print(f"   ✅ Rejected : {stats['rejected']}")
    print(f"   ✅ Par agent :")
    for agent, s in stats["by_agent"].items():
        print(f"      • {agent} : {s}")

    print("\n" + "=" * 70)
    print("✅ TEST TERMINÉ")
    print("=" * 70)


if __name__ == "__main__":
    main()