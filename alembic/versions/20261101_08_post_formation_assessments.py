"""Persist post-training tests, satisfaction surveys and trainer feedback."""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import context, op
from sqlalchemy.dialects import postgresql

revision: str = "20261101_08"
down_revision: str | None = "20261101_07"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    columns = {
        "reponses_test_final": sa.Column("reponses_test_final", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        "score_test_final": sa.Column("score_test_final", sa.Integer(), nullable=True),
        "niveau_final": sa.Column("niveau_final", sa.String(length=30), nullable=True),
        "reponses_satisfaction": sa.Column("reponses_satisfaction", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        "score_satisfaction": sa.Column("score_satisfaction", sa.Integer(), nullable=True),
        "date_evaluation_finale": sa.Column("date_evaluation_finale", sa.DateTime(timezone=True), nullable=True),
    }
    if context.is_offline_mode():
        for column in columns.values():
            op.add_column("inscriptions", column)
        return
    inspector = sa.inspect(op.get_bind())
    if "inscriptions" not in inspector.get_table_names():
        return
    existing = {column["name"] for column in inspector.get_columns("inscriptions")}
    for name, column in columns.items():
        if name not in existing:
            op.add_column("inscriptions", column)


def downgrade() -> None:
    if context.is_offline_mode():
        for name in ("date_evaluation_finale", "score_satisfaction", "reponses_satisfaction", "niveau_final", "score_test_final", "reponses_test_final"):
            op.drop_column("inscriptions", name)
        return
    inspector = sa.inspect(op.get_bind())
    if "inscriptions" not in inspector.get_table_names():
        return
    existing = {column["name"] for column in inspector.get_columns("inscriptions")}
    for name in ("date_evaluation_finale", "score_satisfaction", "reponses_satisfaction", "niveau_final", "score_test_final", "reponses_test_final"):
        if name in existing:
            op.drop_column("inscriptions", name)
