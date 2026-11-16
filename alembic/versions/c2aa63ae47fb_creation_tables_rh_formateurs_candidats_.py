"""creation tables RH formateurs candidats entretiens

Revision ID: c2aa63ae47fb
Revises: 1858c5d99942
Create Date: 2026-09-28 10:03:56.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'c2aa63ae47fb'
down_revision: Union[str, None] = '1858c5d99942'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Création des types ENUM PostgreSQL (IF NOT EXISTS via try/except)
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE statutformateur AS ENUM ('DISPONIBLE', 'OCCUPE', 'INACTIF');
        EXCEPTION WHEN duplicate_object THEN NULL;
        END $$;
    """)
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE recommandationevaluation AS ENUM ('OUI', 'CONDITIONNEL', 'NON');
        EXCEPTION WHEN duplicate_object THEN NULL;
        END $$;
    """)
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE decisionpreselection AS ENUM ('RETENU', 'A_DISCUTER', 'NON_RETENU');
        EXCEPTION WHEN duplicate_object THEN NULL;
        END $$;
    """)
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE decisionentretien AS ENUM ('RECRUTER', 'APPROFONDIR', 'NE_PAS_RECRUTER');
        EXCEPTION WHEN duplicate_object THEN NULL;
        END $$;
    """)

    # Table formateurs
    op.execute("""
        CREATE TABLE IF NOT EXISTS formateurs (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            nom VARCHAR(100) NOT NULL,
            prenom VARCHAR(100),
            email VARCHAR(200),
            telephone VARCHAR(30),
            adresse VARCHAR(300),
            specialite VARCHAR(200),
            tarif_journalier DOUBLE PRECISION,
            statut statutformateur NOT NULL DEFAULT 'DISPONIBLE',
            score_moyen DOUBLE PRECISION,
            nb_sessions VARCHAR(10),
            recommandation recommandationevaluation,
            notes_internes TEXT,
            date_creation TIMESTAMPTZ NOT NULL DEFAULT now()
        );
    """)

    # Table candidats
    op.execute("""
        CREATE TABLE IF NOT EXISTS candidats (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            nom VARCHAR(200) NOT NULL,
            poste_vise VARCHAR(200) NOT NULL,
            cv_texte TEXT,
            score_preselection DOUBLE PRECISION,
            decision_preselection decisionpreselection,
            review_id_preselection VARCHAR(100),
            formateur_id UUID REFERENCES formateurs(id) ON DELETE SET NULL,
            date_creation TIMESTAMPTZ NOT NULL DEFAULT now()
        );
    """)

    # Table entretiens
    op.execute("""
        CREATE TABLE IF NOT EXISTS entretiens (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            candidat_id UUID NOT NULL REFERENCES candidats(id) ON DELETE CASCADE,
            date_entretien TIMESTAMPTZ,
            interviewers VARCHAR(500),
            notes_brutes TEXT,
            compte_rendu TEXT,
            decision decisionentretien,
            review_id_entretien VARCHAR(100),
            email_brouillon TEXT,
            review_id_email VARCHAR(100),
            date_creation TIMESTAMPTZ NOT NULL DEFAULT now()
        );
    """)

    # Index utiles
    op.execute("CREATE INDEX IF NOT EXISTS idx_formateurs_specialite ON formateurs (specialite);")
    op.execute("CREATE INDEX IF NOT EXISTS idx_formateurs_statut ON formateurs (statut);")
    op.execute("CREATE INDEX IF NOT EXISTS idx_candidats_decision ON candidats (decision_preselection);")
    op.execute("CREATE INDEX IF NOT EXISTS idx_candidats_formateur ON candidats (formateur_id);")
    op.execute("CREATE INDEX IF NOT EXISTS idx_entretiens_candidat ON entretiens (candidat_id);")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS entretiens CASCADE;")
    op.execute("DROP TABLE IF EXISTS candidats CASCADE;")
    op.execute("DROP TABLE IF EXISTS formateurs CASCADE;")
    op.execute("DROP TYPE IF EXISTS decisionentretien;")
    op.execute("DROP TYPE IF EXISTS decisionpreselection;")
    op.execute("DROP TYPE IF EXISTS recommandationevaluation;")
    op.execute("DROP TYPE IF EXISTS statutformateur;")
