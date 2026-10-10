# scripts/setup_pgvector.py
# ============================================================
# SETUP — Extension pgvector + Index HNSW
# ============================================================
# Exécution : python scripts/setup_pgvector.py
# ============================================================

import sys
from pathlib import Path

# Ajouter le root au PYTHONPATH
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import text
from app.database import engine


def setup_pgvector():
    print("=" * 70)
    print("🚀 SETUP PGVECTOR — FORMA-IA")
    print("=" * 70)
    
    with engine.connect() as conn:
        # 1. Activer l'extension
        print("\n1️⃣ Activation de l'extension pgvector...")
        try:
            conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector;"))
            conn.commit()
            print("   ✅ Extension activée")
        except Exception as exc:
            print(f"   ❌ Erreur : {exc}")
            print("\n💡 Solution :")
            print("   - PostgreSQL doit être >= 14")
            print("   - pgvector doit être installé sur le serveur")
            print("   - Ubuntu: sudo apt install postgresql-15-pgvector")
            print("   - Windows: télécharger depuis pgvector releases")
            return False
        
        # 2. Vérifier la version
        result = conn.execute(text(
            "SELECT extname, extversion FROM pg_extension WHERE extname = 'vector';"
        )).fetchone()
        
        if result:
            print(f"   ✅ pgvector version {result[1]}")
        else:
            print("   ❌ Extension non trouvée")
            return False
        
        # 3. Vérifier si la table existe (après SQLAlchemy create_all)
        result = conn.execute(text("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_name = 'knowledge_base'
            );
        """)).fetchone()
        
        if not result[0]:
            print("\n⚠️ Table 'knowledge_base' n'existe pas encore.")
            print("   Elle sera créée par SQLAlchemy au démarrage de l'API.")
            print("   Relancez ce script après le premier démarrage.")
            return False
        
        # 4. Créer l'index HNSW
        print("\n2️⃣ Création de l'index HNSW...")
        try:
            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_kb_embedding_hnsw
                ON knowledge_base
                USING hnsw (embedding vector_cosine_ops)
                WITH (m = 16, ef_construction = 64);
            """))
            conn.commit()
            print("   ✅ Index HNSW créé")
        except Exception as exc:
            print(f"   ⚠️ Index HNSW : {exc}")
        
        # 5. Vérifier les index
        result = conn.execute(text("""
            SELECT indexname FROM pg_indexes 
            WHERE tablename = 'knowledge_base';
        """)).fetchall()
        
        print(f"\n   Index sur knowledge_base : {len(result)}")
        for row in result:
            print(f"   • {row[0]}")
    
    print("\n" + "=" * 70)
    print("✅ PGVECTOR PRÊT")
    print("=" * 70)
    return True


if __name__ == "__main__":
    success = setup_pgvector()
    sys.exit(0 if success else 1)