"""renommage de WORD en DOCX dans l'enum formatexport

Revision ID: 0df71f2126b4
Revises: a754a0fdc0f4
Create Date: 2026-09-08 18:15:13.665204

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0df71f2126b4'
down_revision: Union[str, None] = 'a754a0fdc0f4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TYPE formatexport RENAME VALUE 'WORD' TO 'DOCX'")


def downgrade() -> None:
    op.execute("ALTER TYPE formatexport RENAME VALUE 'DOCX' TO 'WORD'")