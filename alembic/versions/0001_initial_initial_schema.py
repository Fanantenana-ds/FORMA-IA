"""initial schema

Revision ID: 0001_initial
Revises: 84c43b7d26ae
Create Date: 2026-10-18 15:59:37.895787

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0001_initial'
down_revision: Union[str, None] = '84c43b7d26ae'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
