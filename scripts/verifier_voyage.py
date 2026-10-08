# scripts/verifier_voyage.py
# ============================================================
# VÉRIFICATION RÉELLE — Provider Voyage AI (embeddings RAG)
# ============================================================
# Un appel réel à l'API Voyage. Affiche les similarités, les modèles
# utilisés, la dimension et les limites configurées. NE JAMAIS afficher
# la clé API.
#
# Critère de réussite RELATIF (les valeurs absolues varient selon les
# modèles) : sim(1,2) > sim(1,3) + 0,15
#   1. "formation en intelligence artificielle"
#   2. "cours de machine learning"          (proche du sujet 1)
#   3. "recette de cuisine"                 (sans rapport)
#
# Exécution : python scripts/verifier_voyage.py
# ============================================================

import asyncio
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from dotenv import load_dotenv
load_dotenv(Path(__file__).resolve().parents[1] / ".env")

from app.services.rag.embedding_provider import get_embedding_provider, EmbeddingProviderError

PHRASES = [
    "formation en intelligence artificielle",
    "cours de machine learning",
    "recette de cuisine",
]


def similarite_cosinus(a: list, b: list) -> float:
    produit = sum(x * y for x, y in zip(a, b))
    norme_a = math.sqrt(sum(x * x for x in a))
    norme_b = math.sqrt(sum(y * y for y in b))
    if norme_a == 0 or norme_b == 0:
        return 0.0
    return produit / (norme_a * norme_b)


async def main() -> bool:
    print("=" * 70)
    print("🧪 VÉRIFICATION VOYAGE AI — FORMA-IA (RAG)")
    print("=" * 70)

    try:
        provider = get_embedding_provider()
    except EmbeddingProviderError as exc:
        print(f"\n❌ Impossible d'initialiser le fournisseur : {exc}")
        return False

    print(f"\n🔧 Modèle document : {provider.modele_document}")
    print(f"🔧 Modèle requête  : {provider.modele_requete}")
    print(f"🔧 Dimension       : {provider.config.dimension}")
    print(f"🔧 Limites         : {provider.config.rpm} RPM / {provider.config.tpm} TPM")

    print(f"\n📤 Embedding de {len(PHRASES)} phrases (mode document)...")
    try:
        vecteurs_doc = await provider.embed_documents(PHRASES)
    except EmbeddingProviderError as exc:
        print(f"\n❌ Échec de l'appel Voyage (mode document) : {exc}")
        return False

    print(f"   ✅ {len(vecteurs_doc)} vecteurs reçus (dimension {len(vecteurs_doc[0])})")

    print("\n📤 Embedding de la phrase 1 (mode requête)...")
    try:
        vecteur_requete = await provider.embed_query(PHRASES[0], attente_max_s=None)
    except EmbeddingProviderError as exc:
        print(f"\n❌ Échec de l'appel Voyage (mode requête) : {exc}")
        return False

    print(f"   ✅ Vecteur requête reçu (dimension {len(vecteur_requete)})")

    sim_1_2 = similarite_cosinus(vecteurs_doc[0], vecteurs_doc[1])
    sim_1_3 = similarite_cosinus(vecteurs_doc[0], vecteurs_doc[2])
    sim_requete_1 = similarite_cosinus(vecteur_requete, vecteurs_doc[0])

    print("\n" + "=" * 70)
    print("📊 SIMILARITÉS (cosinus)")
    print("=" * 70)
    print(f"   sim(doc1, doc2) [IA vs ML]      = {sim_1_2:.4f}")
    print(f"   sim(doc1, doc3) [IA vs cuisine]  = {sim_1_3:.4f}")
    print(f"   sim(requête1, doc1) [asymétrique] = {sim_requete_1:.4f}")
    print(f"   écart sim(1,2) - sim(1,3)        = {sim_1_2 - sim_1_3:.4f}  (seuil : > 0.15)")

    reussite = sim_1_2 > sim_1_3 + 0.15

    print("\n" + "=" * 70)
    if reussite:
        print("✅ VÉRIFICATION RÉUSSIE — les embeddings Voyage discriminent correctement.")
    else:
        print("❌ VÉRIFICATION ÉCHOUÉE — écart de similarité insuffisant.")
    print("=" * 70)

    return reussite


if __name__ == "__main__":
    succes = asyncio.run(main())
    sys.exit(0 if succes else 1)
