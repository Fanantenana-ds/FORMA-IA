"""renommage de score_pertinente en score_pertinence

Revision ID: 4a6b160cc6c7
Revises: 29a9a3ebea9a
Create Date: 2026-08-28 00:10:53.334232

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '4a6b160cc6c7'
down_revision: Union[str, None] = '29a9a3ebea9a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column('opportunites', 'score_pertinente', new_column_name='score_pertinence')
    op.alter_column('historique_analyses', 'score_pertinente', new_column_name='score_pertinence')


def downgrade() -> None:
    op.alter_column('historique_analyses', 'score_pertinence', new_column_name='score_pertinente')
    op.alter_column('opportunites', 'score_pertinence', new_column_name='score_pertinente')