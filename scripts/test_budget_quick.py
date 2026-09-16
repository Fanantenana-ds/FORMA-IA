"""Test rapide BudgetCalculatorService."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.preparation import BudgetCalculatorService


def main():
    print("=" * 60)
    print("🧪 TEST RAPIDE — BudgetCalculator")
    print("=" * 60)

    service = BudgetCalculatorService()

    result = service.calculer(
        formateur_info={"nom": "Rakoto", "tarif_journalier": 500000},
        salle_info={"nom": "Salle A", "tarif_journalier": 200000},
        nb_jours=2,
        nb_participants=20,
    )

    print("\n📊 RÉSULTAT :")
    print(f"   • Formateur     : {result['cout_formateur']:>12,} MGA")
    print(f"   • Salle         : {result['cout_salle']:>12,} MGA")
    print(f"   • Supports      : {result['cout_supports']:>12,} MGA")
    print(f"   • Logistique    : {result['cout_logistique']:>12,} MGA")
    print(f"   • Administration: {result['cout_administration']:>12,} MGA")
    print(f"   ─────────────────────────────")
    print(f"   • TOTAL         : {result['cout_total']:>12,} MGA")

    print("\n✅ Test terminé")


if __name__ == "__main__":
    main()