"""passage de toutes les colonnes datetime en timestamp with timezone

Revision ID: 29a9a3ebea9a
Revises: 6313c4c66d03
Create Date: 2026-08-27 22:46:41.847784

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '29a9a3ebea9a'
down_revision: Union[str, None] = '6313c4c66d03'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE opportunites "
        "ALTER COLUMN date_creation TYPE TIMESTAMP WITH TIME ZONE "
        "USING date_creation AT TIME ZONE 'UTC'"
    )
    op.execute(
        "ALTER TABLE opportunites "
        "ALTER COLUMN echeance TYPE TIMESTAMP WITH TIME ZONE "
        "USING echeance AT TIME ZONE 'UTC'"
    )
    op.execute(
        "ALTER TABLE historique_analyses "
        "ALTER COLUMN date_analyse TYPE TIMESTAMP WITH TIME ZONE "
        "USING date_analyse AT TIME ZONE 'UTC'"
    )
    op.execute(
        "ALTER TABLE historique_analyses "
        "ALTER COLUMN echeance TYPE TIMESTAMP WITH TIME ZONE "
        "USING echeance AT TIME ZONE 'UTC'"
    )


def downgrade() -> None:
    op.execute(
        "ALTER TABLE historique_analyses "
        "ALTER COLUMN echeance TYPE TIMESTAMP WITHOUT TIME ZONE"
    )
    op.execute(
        "ALTER TABLE historique_analyses "
        "ALTER COLUMN date_analyse TYPE TIMESTAMP WITHOUT TIME ZONE"
    )
    op.execute(
        "ALTER TABLE opportunites "
        "ALTER COLUMN echeance TYPE TIMESTAMP WITHOUT TIME ZONE"
    )
    op.execute(
        "ALTER TABLE opportunites "
        "ALTER COLUMN date_creation TYPE TIMESTAMP WITHOUT TIME ZONE"
    )