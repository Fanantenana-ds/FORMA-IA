"""creation de la table documents (TDR, Offre, Attestation)

Revision ID: f8a371d13349
Revises: 4a6b160cc6c7
Create Date: 2026-08-28 15:04:45.677350

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'f8a371d13349'
down_revision: Union[str, None] = '4a6b160cc6c7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None



def upgrade() -> None:
    op.create_table(
        "documents",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "type",
            sa.Enum("TDR", "OFFRE", "ATTESTATION", name="typedocument"),
            nullable=False
        ),
        sa.Column("contenu", sa.Text(), nullable=False),
        sa.Column(
            "format_export",
            sa.Enum("WORD", "PDF", name="formatexport"),
            nullable=True
        ),
        sa.Column(
            "statut_validation",
            sa.Enum("EN_ATTENTE", "VALIDE", "REJETE", name="statutvalidation"),
            nullable=False,
            server_default="EN_ATTENTE"
        ),
        sa.Column("valide_par", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("date_generation", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("date_validation", sa.DateTime(timezone=True), nullable=True),

        # Colonnes spécifiques TDR
        sa.Column("client", sa.String(255), nullable=True),
        sa.Column("objectifs", sa.Text(), nullable=True),

        # Colonnes spécifiques Offre
        sa.Column("opportunite_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("opportunites.id"), nullable=True),
        sa.Column("montant", sa.Float(), nullable=True),

        # Colonnes spécifiques Attestation
        # Pas de ForeignKey vers sessions/participants pour l'instant :
        # ces tables n'existent pas encore (module Formations à venir).
        sa.Column("session_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("participant_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("numero_unique", sa.String(50), nullable=True, unique=True),
    )


def downgrade() -> None:
    op.drop_table("documents")
    op.execute("DROP TYPE IF EXISTS typedocument")
    op.execute("DROP TYPE IF EXISTS formatexport")
    op.execute("DROP TYPE IF EXISTS statutvalidation")