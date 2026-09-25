# scripts/finaliser_schema_knowledge_base.py
# ============================================================
# MIGRATION — knowledge_base : schéma final Étape C (RAG)
# ============================================================
# Passe du schéma provisoire (Étape B : juste embedding en 1024) au schéma
# final : collection, doc_hash, formation_code, page_debut/page_fin,
# modele_embed, etc. (voir app/models/knowledge_base.py).
#
# Table non suivie par Alembic (voir constat Étape A) : migration SQL
# directe, comme sa création initiale. Garde-fou : refuse si la table
# contient des données (DROP+CREATE, donc destructif si non vide).
#
# Exécution : python scripts/finaliser_schema_knowledge_base.py
# ============================================================

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import text
from app.database import engine
from app.models.knowledge_base import KnowledgeBase

INDEX_NAME = "idx_kb_embedding_hnsw"


def migrer() -> bool:
    print("=" * 70)
    print("🔄 FINALISATION DU SCHÉMA — knowledge_base (Étape C, RAG)")
    print("=" * 70)

    with engine.connect() as conn:
        nb_lignes = conn.execute(text("SELECT count(*) FROM knowledge_base")).scalar()
        print(f"\n1️⃣ Lignes actuelles : {nb_lignes}")

        if nb_lignes and nb_lignes > 0:
            print("   ❌ ARRÊT : la table contient des données. Migration refusée.")
            return False

        print("   ✅ Table vide, migration autorisée (DROP + CREATE).")

        print("\n2️⃣ Suppression de la table et de son index...")
        conn.execute(text(f"DROP INDEX IF EXISTS {INDEX_NAME};"))
        conn.execute(text("DROP TABLE IF EXISTS knowledge_base;"))
        conn.commit()
        print("   ✅ Table supprimée.")

    print("\n3️⃣ Recréation de la table (schéma final, via SQLAlchemy)...")
    KnowledgeBase.__table__.create(bind=engine)
    print("   ✅ Table recréée.")

    with engine.connect() as conn:
        print(f"\n4️⃣ Recréation de l'index {INDEX_NAME}...")
        conn.execute(text(f"""
            CREATE INDEX {INDEX_NAME}
            ON knowledge_base
            USING hnsw (embedding vector_cosine_ops)
            WITH (m = 16, ef_construction = 64);
        """))
        conn.commit()
        print("   ✅ Index créé.")

        print("\n5️⃣ Vérification des colonnes...")
        colonnes = conn.execute(text("""
            SELECT column_name FROM information_schema.columns
            WHERE table_name = 'knowledge_base' ORDER BY ordinal_position;
        """)).fetchall()
        noms = [c[0] for c in colonnes]
        print("   Colonnes :", ", ".join(noms))

        attendu = {
            "id", "collection", "doc_hash", "fichier", "formation_code",
            "formation_titre", "domaine", "annee", "type_support",
            "page_debut", "page_fin", "chunk_index", "contenu", "embedding",
            "modele_embed", "meta", "created_at",
        }
        manquantes = attendu - set(noms)
        if manquantes:
            print(f"   ❌ Colonnes manquantes : {manquantes}")
            return False

    print("\n" + "=" * 70)
    print("✅ SCHÉMA FINALISÉ")
    print("=" * 70)
    return True


if __name__ == "__main__":
    succes = migrer()
    sys.exit(0 if succes else 1)
