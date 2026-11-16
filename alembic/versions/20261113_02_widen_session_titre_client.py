"""Élargit sessions.titre et sessions.client à 200 caractères."""

import sqlalchemy as sa
from alembic import op

revision: str = "20261113_02"
down_revision: str | None = "20261113_01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column("sessions", "titre", existing_type=sa.String(50), type_=sa.String(200), existing_nullable=False)
    op.alter_column("sessions", "client", existing_type=sa.String(50), type_=sa.String(200), existing_nullable=True)


def downgrade() -> None:
    op.alter_column("sessions", "client", existing_type=sa.String(200), type_=sa.String(50), existing_nullable=True)
    op.alter_column("sessions", "titre", existing_type=sa.String(200), type_=sa.String(50), existing_nullable=False)
