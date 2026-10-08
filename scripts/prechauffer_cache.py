# scripts/prechauffer_cache.py
# ============================================================
# PRÉCHAUFFAGE DU CACHE DE REQUÊTES — avant une démonstration (Étape D)
# ============================================================
# Calcule et met en cache les embeddings des questions de
# data/rag/questions_demo.yaml, en respectant le limiteur de débit Voyage
# (aucune limite d'attente : script interactif, pas le chat).
#
# Exécution : python scripts/prechauffer_cache.py [chemin_questions.yaml]
# ============================================================

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from dotenv import load_dotenv
load_dotenv(Path(__file__).resolve().parents[1] / ".env")

import yaml

from app.services.rag.embedding_provider import get_embedding_provider, EmbeddingProviderError
from app.services.rag.query_cache_service import (
    depuis_cache, obtenir_ou_calculer, taille_cache, CHEMIN_CACHE_DEFAUT,
)

CHEMIN_QUESTIONS_DEFAUT = Path(__file__).resolve().parents[1] / "data" / "rag" / "questions_demo.yaml"


async def main(chemin_questions: Path) -> bool:
    print("=" * 70)
    print("🔥 PRÉCHAUFFAGE DU CACHE DE REQUÊTES — FORMA-IA (RAG)")
    print("=" * 70)

    if not chemin_questions.exists():
        print(f"\n❌ Fichier introuvable : {chemin_questions}")
        return False

    with open(chemin_questions, "r", encoding="utf-8") as f:
        questions = (yaml.safe_load(f) or {}).get("questions") or []

    if not questions:
        print(f"\n❌ Aucune question dans {chemin_questions}.")
        return False

    print(f"\n📋 {len(questions)} question(s) à préchauffer.")
    print(f"💾 Cache actuel : {taille_cache()} entrée(s).")

    try:
        provider = get_embedding_provider()
    except EmbeddingProviderError as exc:
        print(f"\n❌ {exc}")
        return False

    deja_en_cache = 0
    nouveaux = 0

    async def _embed(texte, **kw):
        return await provider.embed_query(texte, **kw)

    for i, question in enumerate(questions, start=1):
        if depuis_cache(question, provider.modele_requete) is not None:
            print(f"   [{i}/{len(questions)}] 💾 Déjà en cache : {question[:60]}")
            deja_en_cache += 1
            continue

        print(f"   [{i}/{len(questions)}] 📤 Calcul... : {question[:60]}")
        await obtenir_ou_calculer(
            question, provider.modele_requete, _embed,
            chemin=CHEMIN_CACHE_DEFAUT, attente_max_s=None,  # script interactif : attend si besoin
        )
        nouveaux += 1

    print("\n" + "=" * 70)
    print(f"✅ TERMINÉ — {nouveaux} nouvelle(s) entrée(s), {deja_en_cache} déjà en cache.")
    print(f"💾 Cache final : {taille_cache()} entrée(s).")
    print("=" * 70)
    return True


if __name__ == "__main__":
    chemin = Path(sys.argv[1]) if len(sys.argv) > 1 else CHEMIN_QUESTIONS_DEFAUT
    succes = asyncio.run(main(chemin))
    sys.exit(0 if succes else 1)
