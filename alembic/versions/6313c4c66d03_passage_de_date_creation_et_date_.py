"""passage de date_creation et date_analyse en timestamp with timezone

Revision ID: 6313c4c66d03
Revises: b3b9b66b5f88
Create Date: 2026-08-27 22:43:01.041651

"""
from collections.abc import Sequence

# revision identifiers, used by Alembic.
revision: str = '6313c4c66d03'
down_revision: str | None = 'b3b9b66b5f88'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
