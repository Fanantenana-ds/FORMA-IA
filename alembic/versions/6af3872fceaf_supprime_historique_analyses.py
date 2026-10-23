"""supprime historique_analyses

Revision ID: 6af3872fceaf
Revises: 0001_initial
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "6af3872fceaf"
down_revision: str | None = "0001_initial"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    if sa.inspect(op.get_bind()).has_table("historique_analyses"):
        op.drop_table("historique_analyses")


def downgrade() -> None:
    raise NotImplementedError("suppression volontairement irréversible")
