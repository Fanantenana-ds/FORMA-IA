"""Allow full training titles in session themes."""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20261101_03"
down_revision: str | None = "20261101_02"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column(
        "seances", "theme",
        existing_type=sa.String(length=100),
        type_=sa.String(length=500),
        existing_nullable=False,
    )


def downgrade() -> None:
    op.alter_column(
        "seances", "theme",
        existing_type=sa.String(length=500),
        type_=sa.String(length=100),
        existing_nullable=False,
    )
