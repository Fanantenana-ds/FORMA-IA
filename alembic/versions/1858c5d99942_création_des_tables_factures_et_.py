"""création des tables factures et paiements

Revision ID: 1858c5d99942
Revises: 0df71f2126b4
Create Date: 2026-09-11 14:55:59.473987

"""
from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '1858c5d99942'
down_revision: str | None = '0df71f2126b4'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    statut = postgresql.ENUM(
        "EMISE", "PARTIELLEMENT_PAYEE", "PAYEE", "EN_RETARD", "ANNULEE",
        name="statutfacture",
    )
    op.create_table(
        "factures",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("numero", sa.String(50), nullable=False, unique=True),
        sa.Column("client", sa.String(50), nullable=False),
        sa.Column("montant", sa.Float, nullable=False),
        sa.Column("tva_taux", sa.Float, nullable=False),
        sa.Column("statut", statut, nullable=False),
        sa.Column("date_emission", sa.DateTime(timezone=True), nullable=False),
        sa.Column("date_echeance", sa.Date, nullable=True),
    )
    op.create_table(
        "paiements",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("facture_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("factures.id"), nullable=False),
        sa.Column("montant", sa.Float, nullable=False),
        sa.Column("date", sa.Date, nullable=False),
        sa.Column("mode", sa.String(20), nullable=True),
    )
    op.create_table(
        "relances",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("facture_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("factures.id"), nullable=False),
        sa.Column("niveau", sa.String(1), nullable=False),
        sa.Column("objet", sa.String(200), nullable=False),
        sa.Column("texte", sa.String(10000), nullable=False),
        sa.Column("review_id", sa.String(100), nullable=True),
        sa.Column("date_creation", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("relances")
    op.drop_table("paiements")
    op.drop_table("factures")
    op.execute("DROP TYPE IF EXISTS statutfacture")