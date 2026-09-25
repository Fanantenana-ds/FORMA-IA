# scripts/generer_resumes.py
# ============================================================
# GÉNÉRATION DES RÉSUMÉS MANQUANTS — Étape C §11
# ============================================================
# Génère les résumés (Groq) des documents déjà indexés mais dont le
# résumé a échoué (resume_statut='a_generer') — SANS jamais rappeler
# Voyage : les chunks et leurs embeddings sont déjà en base, seul le
# texte relu depuis le fichier original (data/rag/fichiers/) est
# ré-envoyé à Groq.
#
# Exécution : python scripts/generer_resumes.py
# ============================================================

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from dotenv import load_dotenv
load_dotenv(Path(__file__).resolve().parents[1] / ".env")

from app.services.rag import registry_service as registre
from app.services.rag.document_loader_service import extract_segments, detect_file_type
from app.services.rag.text_cleaner_service import clean_text
from app.services.rag.document_loader_service import Segment
from app.services.rag.resume_service import generer_resume_support

DOSSIER_FICHIERS_ORIGINAUX = Path(__file__).resolve().parents[1] / "data" / "rag" / "fichiers"


async def main() -> bool:
    print("=" * 70)
    print("📝 GÉNÉRATION DES RÉSUMÉS MANQUANTS — FORMA-IA (RAG)")
    print("=" * 70)

    entrees = registre.entrees_sans_resume()
    if not entrees:
        print("\n✅ Aucun résumé manquant — rien à faire.")
        return True

    print(f"\n📋 {len(entrees)} document(s) sans résumé.\n")

    reussis = 0
    echecs = 0

    for i, entree in enumerate(entrees, start=1):
        print(f"[{i}/{len(entrees)}] {entree.fichier} (formation={entree.formation_code or 'aucune'})...")

        candidats = list(DOSSIER_FICHIERS_ORIGINAUX.glob(f"{entree.hash}.*"))
        if not candidats:
            print(f"   ❌ Fichier original introuvable ({entree.hash}), ignoré.")
            echecs += 1
            continue

        chemin_original = candidats[0]
        type_fichier = detect_file_type(str(chemin_original))

        try:
            segments = extract_segments(str(chemin_original), type_fichier)
        except Exception as exc:
            print(f"   ❌ Ré-extraction échouée : {exc}")
            echecs += 1
            continue

        segments_propres = [Segment(numero=s.numero, texte=clean_text(s.texte)) for s in segments]
        resultat = await generer_resume_support(segments_propres, entree.fichier)

        if resultat and resultat.get("resume"):
            entree.resume = resultat.get("resume")
            entree.plan = resultat.get("plan", [])
            entree.mots_cles = resultat.get("mots_cles", [])
            entree.resume_statut = "genere"
            registre.enregistrer_entree(entree)
            print("   ✅ Résumé généré.")
            reussis += 1
        else:
            print("   ⚠️ Échec Groq à nouveau — resume_statut reste 'a_generer'.")
            echecs += 1

    print("\n" + "=" * 70)
    print(f"✅ TERMINÉ — {reussis} résumé(s) généré(s), {echecs} échec(s) restant(s).")
    print("=" * 70)
    return True


if __name__ == "__main__":
    succes = asyncio.run(main())
    sys.exit(0 if succes else 1)
