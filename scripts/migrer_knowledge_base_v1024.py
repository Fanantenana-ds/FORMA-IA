# scripts/migrer_knowledge_base_v1024.py
# ============================================================
# MIGRATION — knowledge_base.embedding : Vector(384) -> Vector(1024)
# ============================================================
# Passage à Voyage AI (voyage-4-large, output_dimension=1024). Cette table
# n'est pas suivie par Alembic (créée via Base.metadata.create_all(), comme
# scripts/setup_pgvector.py) : migration en SQL direct, même méthode que sa
# création initiale.
#
# Garde-fou : refuse de migrer si la table contient déjà des lignes (aucune
# perte de données silencieuse). Étape B de la mission C3 : migre UNIQUEMENT
# la dimension du vecteur, pas le reste du schéma (collection, doc_hash,
# formation_code, etc. — prévu à l'Étape C, quand le pipeline d'ingestion
# qui les consomme sera écrit).
#
# Exécution : python scripts/migrer_knowledge_base_v1024.py
# ============================================================

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import text
from app.database import engine

INDEX_NAME = "idx_kb_embedding_hnsw"


def migrer() -> bool:
    print("=" * 70)
    print("🔄 MIGRATION — knowledge_base.embedding : vector(384) -> vector(1024)")
    print("=" * 70)

    with engine.connect() as conn:
        # 1. Garde-fou : table vide ?
        nb_lignes = conn.execute(text("SELECT count(*) FROM knowledge_base")).scalar()
        print(f"\n1️⃣ Lignes actuelles dans knowledge_base : {nb_lignes}")

        if nb_lignes and nb_lignes > 0:
            print(
                "   ❌ ARRÊT : la table contient déjà des données. "
                "Migration refusée pour éviter toute perte silencieuse."
            )
            return False

        print("   ✅ Table vide, migration autorisée.")

        # 2. Vérifier la dimension actuelle
        dim_actuelle = conn.execute(text("""
            SELECT atttypmod FROM pg_attribute
            WHERE attrelid = 'knowledge_base'::regclass AND attname = 'embedding';
        """)).scalar()
        print(f"\n2️⃣ Dimension actuelle déclarée : {dim_actuelle}")

        if dim_actuelle == 1024:
            print("   ℹ️ Déjà en dimension 1024, rien à faire.")
            return True

        # 3. Supprimer l'index HNSW (dimension liée à l'index)
        print(f"\n3️⃣ Suppression de l'index {INDEX_NAME}...")
        conn.execute(text(f"DROP INDEX IF EXISTS {INDEX_NAME};"))
        conn.commit()
        print("   ✅ Index supprimé (ou absent).")

        # 4. Changer la dimension de la colonne
        print("\n4️⃣ Changement de dimension de la colonne embedding...")
        conn.execute(text(
            "ALTER TABLE knowledge_base "
            "ALTER COLUMN embedding TYPE vector(1024);"
        ))
        conn.commit()
        print("   ✅ Colonne migrée en vector(1024).")

        # 5. Recréer l'index HNSW
        print(f"\n5️⃣ Recréation de l'index {INDEX_NAME}...")
        conn.execute(text(f"""
            CREATE INDEX {INDEX_NAME}
            ON knowledge_base
            USING hnsw (embedding vector_cosine_ops)
            WITH (m = 16, ef_construction = 64);
        """))
        conn.commit()
        print("   ✅ Index recréé.")

        # 6. Vérification finale
        dim_finale = conn.execute(text("""
            SELECT atttypmod FROM pg_attribute
            WHERE attrelid = 'knowledge_base'::regclass AND attname = 'embedding';
        """)).scalar()
        index_present = conn.execute(text("""
            SELECT EXISTS (
                SELECT FROM pg_indexes
                WHERE tablename = 'knowledge_base' AND indexname = :nom
            );
        """), {"nom": INDEX_NAME}).scalar()

        print(f"\n6️⃣ Vérification : dimension={dim_finale}, index_present={index_present}")

        if dim_finale != 1024 or not index_present:
            print("   ❌ Vérification échouée après migration.")
            return False

    print("\n" + "=" * 70)
    print("✅ MIGRATION TERMINÉE")
    print("=" * 70)
    return True


if __name__ == "__main__":
    succes = migrer()
    sys.exit(0 if succes else 1)
