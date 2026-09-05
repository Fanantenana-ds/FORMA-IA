"""ajout des contraintes FK session_id et participant_id sur documents

Revision ID: a754a0fdc0f4
Revises: bd5a74464171
Create Date: 2026-09-05 17:21:24.675681

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a754a0fdc0f4'
down_revision: Union[str, None] = 'bd5a74464171'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_foreign_key(
        "fk_documents_session_id",
        "documents", "sessions",
        ["session_id"], ["id"]
    )
    op.create_foreign_key(
        "fk_documents_participant_id",
        "documents", "participants",
        ["participant_id"], ["id"]
    )


def downgrade() -> None:
    op.drop_constraint("fk_documents_participant_id", "documents", type_="foreignkey")
    op.drop_constraint("fk_documents_session_id", "documents", type_="foreignkey")