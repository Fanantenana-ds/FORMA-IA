"""
scripts/creer_table_relances.py
================================
Crée la table `relances` dans la base formaia (même pattern que
scripts/migrer_knowledge_base_v1024.py — SQL direct, pas Alembic).

Usage :
    python scripts/creer_table_relances.py

Idempotent : ne fait rien si la table existe déjà.
"""
import sys
from sqlalchemy import text
from app.database import engine


def main() -> None:
    with engine.connect() as conn:
        exists = conn.execute(text(
            "SELECT EXISTS (SELECT 1 FROM information_schema.tables "
            "WHERE table_name = 'relances')"
        )).scalar()

        if exists:
            print("✅ Table 'relances' existe déjà — rien à faire.")
            return

        print("🔧 Création de la table 'relances'...")
        conn.execute(text("""
            CREATE TABLE relances (
                id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                facture_id   UUID NOT NULL REFERENCES factures(id) ON DELETE CASCADE,
                niveau       VARCHAR(1) NOT NULL CHECK (niveau IN ('1','2','3')),
                objet        VARCHAR(200) NOT NULL,
                texte        VARCHAR(10000) NOT NULL,
                review_id    VARCHAR(100),
                date_creation TIMESTAMPTZ NOT NULL DEFAULT NOW()
            );
            CREATE INDEX idx_relances_facture_id ON relances(facture_id);
        """))
        conn.commit()
        print("✅ Table 'relances' créée avec succès.")

        count = conn.execute(text("SELECT COUNT(*) FROM relances")).scalar()
        print(f"   Lignes actuelles : {count}")


if __name__ == "__main__":
    main()
    sys.exit(0)
