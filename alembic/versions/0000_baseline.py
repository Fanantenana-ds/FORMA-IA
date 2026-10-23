"""baseline : schéma antérieur à 90e0fbb8d168

historique_analyses est un STUB transitoire : seules les colonnes touchées par
les migrations suivantes y figurent. La table est supprimée en fin de chaîne.
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql as pg

revision = "0000_baseline"
down_revision = None
branch_labels = None
depends_on = None


def _enum(name, *vals):
    return pg.ENUM(*vals, name=name, create_type=False)


ROLE     = _enum("role_enum", "DIRECTION", "ASSISTANT", "COMPTABLE", "FORMATEUR")
DOMAINE  = _enum("domaine", "DEVOPS", "DEVELOPPEMENT", "IA", "DATA", "AUTRE")  # sans BUREAUTIQUE
SRC_OLD  = _enum("sourceoppotunite", "TEXTE", "PDF", "URL")
STAT_OLD = _enum("statutoppoetunite", "EN_ATTENTE", "ANALYSEE", "ARCHIVEE")
SRC_NEW  = _enum("sourceopportunite", "TEXTE", "PDF", "URL")
STAT_NEW = _enum("statutopportunite", "EN_ATTENTE", "ANALYSEE", "ARCHIVEE")
ALL_ENUMS = (ROLE, DOMAINE, SRC_OLD, STAT_OLD, SRC_NEW, STAT_NEW)


def upgrade() -> None:
    bind = op.get_bind()
    for e in ALL_ENUMS:
        e.create(bind, checkfirst=True)

    op.create_table(
        "users",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("nom", sa.String(50), nullable=False),
        sa.Column("email", sa.String(50), nullable=False),
        sa.Column("password", sa.String(255), nullable=False),
        sa.Column("role", ROLE, nullable=False),
        sa.Column("actif", sa.Boolean()),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)
    op.create_index("ix_users_id", "users", ["id"])

    op.create_table(
        "opportunites",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("source", SRC_OLD, nullable=False),
        sa.Column("contenu", sa.Text(), nullable=False),
        sa.Column("objet", sa.String(255)),
        sa.Column("budget", sa.Float()),
        sa.Column("echeance", sa.DateTime()),
        sa.Column("domaine", DOMAINE),
        sa.Column("score_pertinente", sa.Float()),
        sa.Column("statut", STAT_OLD, nullable=False),
        sa.Column("date_creation", sa.DateTime(), nullable=False),
    )

    op.create_table(
        "historique_analyses",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("score_pertinente", sa.Float()),
        sa.Column("echeance", sa.DateTime()),
    )


def downgrade() -> None:
    op.drop_table("historique_analyses")
    op.drop_table("opportunites")
    op.drop_table("users")
    for e in ALL_ENUMS:
        e.drop(op.get_bind(), checkfirst=True)