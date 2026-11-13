"""Add DEVIS_TRANSMIS and GAGNEE to StatutOpportunite enum."""
from collections.abc import Sequence

from alembic import op

revision: str = "20261113_01"
down_revision: str | None = "20261107_01"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("ALTER TYPE statutopportunite ADD VALUE IF NOT EXISTS 'DEVIS_TRANSMIS'")
    op.execute("ALTER TYPE statutopportunite ADD VALUE IF NOT EXISTS 'GAGNEE'")


def downgrade() -> None:
    # PostgreSQL does not support removing enum values; downgrade is a no-op.
    pass
