# Scripts/tester_extraction_cv.py
# ============================================================
# TEST MANUEL — Extraction texte CV avec ton propre fichier
#
# Usage :
#   python Scripts/tester_extraction_cv.py "C:\chemin\vers\ton_cv.pdf"
#   python Scripts/tester_extraction_cv.py "C:\chemin\vers\ton_cv.docx"
#   python Scripts/tester_extraction_cv.py "C:\chemin\vers\ton_cv.jpg"
# ============================================================

import asyncio
import sys
import os
from pathlib import Path

# Ajoute le backend au path Python
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

# Charge le .env
from dotenv import load_dotenv
load_dotenv(Path(__file__).resolve().parents[1] / ".env")


async def main():
    if len(sys.argv) < 2:
        print("❌ Usage : python Scripts/tester_extraction_cv.py <chemin_du_cv>")
        print("   Exemple : python Scripts/tester_extraction_cv.py C:\\Users\\moi\\cv.pdf")
        sys.exit(1)

    chemin = Path(sys.argv[1])

    if not chemin.exists():
        print(f"❌ Fichier introuvable : {chemin}")
        sys.exit(1)

    print("=" * 60)
    print(f"📄 Fichier    : {chemin.name}")
    print(f"📦 Taille     : {chemin.stat().st_size / 1024:.1f} Ko")
    print(f"🔤 Extension  : {chemin.suffix.lower()}")
    print("=" * 60)

    contenu = chemin.read_bytes()

    from app.services.rh.cv_extractor_service import extraire_texte_cv, SEUIL_TEXTE_MIN

    print("\n⏳ Extraction en cours...\n")
    texte, methode, lisible = await extraire_texte_cv(contenu, chemin.name)

    print("=" * 60)
    print(f"✅ Méthode utilisée  : {methode}")
    print(f"📊 Longueur texte    : {len(texte)} caractères")
    print(f"🔍 Lisible (LLM)     : {'✅ OUI' if lisible else '❌ NON'}")
    print("=" * 60)

    if not lisible:
        print("\n⚠️  Le LLM considère ce texte comme non exploitable.")
        print("    → Essaie avec un CV en meilleure qualité.")
    else:
        print("\n📝 APERÇU DU TEXTE EXTRAIT (500 premiers chars) :")
        print("-" * 60)
        print(texte[:500])
        print("-" * 60)

        if len(texte) > 500:
            print(f"\n... (+{len(texte) - 500} caractères supplémentaires)")

        print(f"\n✅ Prêt à envoyer à A1 pour présélection.")

    # Sauvegarde optionnelle du texte extrait
    sortie = chemin.with_suffix(".texte_extrait.txt")
    sortie.write_text(texte, encoding="utf-8")
    print(f"\n💾 Texte complet sauvegardé dans : {sortie}")


if __name__ == "__main__":
    asyncio.run(main())
