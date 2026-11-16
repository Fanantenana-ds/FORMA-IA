"""ajout de BUREAUTIQUE dans l'enum domaine

Revision ID: b3b9b66b5f88
Revises: 90e0fbb8d168
Create Date: 2026-08-27 21:44:19.184706

"""
from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'b3b9b66b5f88'
down_revision: str | None = '90e0fbb8d168'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE opportunites "
        "ALTER COLUMN date_creation TYPE TIMESTAMP WITH TIME ZONE "
        "USING date_creation AT TIME ZONE 'UTC'"
    )
    op.execute(
        "ALTER TABLE historique_analyses "
        "ALTER COLUMN date_analyse TYPE TIMESTAMP WITH TIME ZONE "
        "USING date_analyse AT TIME ZONE 'UTC'"
    )


def downgrade() -> None:
    op.execute(
        "ALTER TABLE historique_analyses "
        "ALTER COLUMN date_analyse TYPE TIMESTAMP WITHOUT TIME ZONE"
    )
    op.execute(
        "ALTER TABLE opportunites "
        "ALTER COLUMN date_creation TYPE TIMESTAMP WITHOUT TIME ZONE"
    )