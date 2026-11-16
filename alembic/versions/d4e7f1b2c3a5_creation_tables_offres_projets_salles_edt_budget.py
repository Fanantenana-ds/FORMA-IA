"""creation tables offres projets salles edt budget

Revision ID: d4e7f1b2c3a5
Revises: c2aa63ae47fb
Create Date: 2026-09-28 11:05:00.000000

"""
from typing import Sequence, Union
from alembic import op

revision: str = 'd4e7f1b2c3a5'
down_revision: Union[str, None] = 'c2aa63ae47fb'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── ENUMS ────────────────────────────────────────────────
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE statutoffre AS ENUM ('BROUILLON','EN_ATTENTE','ENVOYEE','ACCEPTEE','REFUSEE');
        EXCEPTION WHEN duplicate_object THEN NULL; END $$;
    """)
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE statutprojet AS ENUM ('BROUILLON','EN_COURS','VALIDE','TERMINE','ANNULE');
        EXCEPTION WHEN duplicate_object THEN NULL; END $$;
    """)

    # ── TABLE offres ─────────────────────────────────────────
    op.execute("""
        CREATE TABLE IF NOT EXISTS offres (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            opportunite_id UUID REFERENCES opportunites(id) ON DELETE SET NULL,
            tdr_document_id UUID REFERENCES documents(id) ON DELETE SET NULL,
            titre VARCHAR(255) NOT NULL,
            client VARCHAR(100) NOT NULL,
            description TEXT,
            trame_technique TEXT,
            trame_financiere TEXT,
            montant_ht DOUBLE PRECISION,
            tva_taux DOUBLE PRECISION NOT NULL DEFAULT 20.0,
            statut statutoffre NOT NULL DEFAULT 'BROUILLON',
            date_creation TIMESTAMPTZ NOT NULL DEFAULT now(),
            date_modification TIMESTAMPTZ
        );
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_offres_statut ON offres (statut);")
    op.execute("CREATE INDEX IF NOT EXISTS idx_offres_opportunite ON offres (opportunite_id);")

    # ── TABLE salles ─────────────────────────────────────────
    op.execute("""
        CREATE TABLE IF NOT EXISTS salles (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            nom VARCHAR(100) NOT NULL,
            adresse VARCHAR(255),
            capacite INTEGER,
            tarif_journalier DOUBLE PRECISION,
            equipements TEXT,
            disponible BOOLEAN NOT NULL DEFAULT TRUE,
            date_creation TIMESTAMPTZ NOT NULL DEFAULT now()
        );
    """)

    # ── TABLE projets ────────────────────────────────────────
    op.execute("""
        CREATE TABLE IF NOT EXISTS projets (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            opportunite_id UUID REFERENCES opportunites(id) ON DELETE SET NULL,
            offre_id UUID REFERENCES offres(id) ON DELETE SET NULL,
            titre VARCHAR(100) NOT NULL,
            client VARCHAR(100),
            date_debut DATE,
            date_fin DATE,
            statut statutprojet NOT NULL DEFAULT 'BROUILLON',
            notes TEXT,
            date_creation TIMESTAMPTZ NOT NULL DEFAULT now()
        );
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_projets_statut ON projets (statut);")

    # ── TABLE edt_sessions ───────────────────────────────────
    op.execute("""
        CREATE TABLE IF NOT EXISTS edt_sessions (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            projet_id UUID NOT NULL REFERENCES projets(id) ON DELETE CASCADE,
            date DATE NOT NULL,
            heure_debut TIME,
            heure_fin TIME,
            module VARCHAR(200),
            formateur_id UUID REFERENCES formateurs(id) ON DELETE SET NULL,
            salle_id UUID REFERENCES salles(id) ON DELETE SET NULL
        );
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_edt_projet ON edt_sessions (projet_id);")

    # ── TABLE budgets_formation ──────────────────────────────
    op.execute("""
        CREATE TABLE IF NOT EXISTS budgets_formation (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            projet_id UUID NOT NULL UNIQUE REFERENCES projets(id) ON DELETE CASCADE,
            cout_formateur DOUBLE PRECISION NOT NULL DEFAULT 0,
            cout_salle DOUBLE PRECISION NOT NULL DEFAULT 0,
            cout_supports DOUBLE PRECISION NOT NULL DEFAULT 0,
            cout_total DOUBLE PRECISION NOT NULL DEFAULT 0,
            valide BOOLEAN NOT NULL DEFAULT FALSE,
            valide_par UUID REFERENCES users(id) ON DELETE SET NULL,
            date_creation TIMESTAMPTZ NOT NULL DEFAULT now()
        );
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS budgets_formation CASCADE;")
    op.execute("DROP TABLE IF EXISTS edt_sessions CASCADE;")
    op.execute("DROP TABLE IF EXISTS projets CASCADE;")
    op.execute("DROP TABLE IF EXISTS salles CASCADE;")
    op.execute("DROP TABLE IF EXISTS offres CASCADE;")
    op.execute("DROP TYPE IF EXISTS statutprojet;")
    op.execute("DROP TYPE IF EXISTS statutoffre;")
