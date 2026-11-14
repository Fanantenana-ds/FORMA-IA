"""factures_client_varchar_300

Revision ID: 3df1b3e09e66
Revises: 20261113_02
Create Date: 2026-11-15 02:30:23.500216

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = '3df1b3e09e66'
down_revision: Union[str, None] = '20261113_02'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column('factures', 'client', type_=sa.String(300), existing_type=sa.String(50), existing_nullable=False)


def downgrade() -> None:
    op.alter_column('factures', 'client', type_=sa.String(50), existing_type=sa.String(300), existing_nullable=False)
