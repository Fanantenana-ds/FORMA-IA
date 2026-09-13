"""création des tables factures et paiements

Revision ID: 1858c5d99942
Revises: 0df71f2126b4
Create Date: 2026-09-11 14:55:59.473987

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = '1858c5d99942'
down_revision: Union[str, None] = '0df71f2126b4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'factures',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('numero', sa.String(50), nullable=False, unique=True),
        sa.Column('client', sa.String(50), nullable=False),
        sa.Column('montant', sa.Float, nullable=False),
        sa.Column('tva_taux', sa.Float, nullable=False, default=20.0),
        sa.Column(
            'statut',
            sa.Enum('EMISE', 'PARTIELLEMENT_PAYEE', 'PAYEE', 'EN_RETARD', name="statutfacture"),
            nullable=False,
            server_default="EMISE"
        ),


        op.create_table(
            "paiements",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
            sa.Column("facture_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("factures.id"), nullable=False),
            sa.Column("montant", sa.Float(), nullable=False),
            sa.Column("date", sa.Date(), nullable=False),
            sa.Column("mode", sa.String(50), nullable=True)
        )

    )


    
def downgrade() -> None:
    op.drop_table("paiements")
    op.drop_table("factures")
    op.execut("DROP TYPE IF EXISTS statutfacture")