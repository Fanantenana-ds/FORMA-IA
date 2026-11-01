"""Add public pre-training assessment storage without replacing registrations."""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import context, op
from sqlalchemy.dialects import postgresql

revision: str = "20261101_04"
down_revision: str | None = "20261101_03"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _add_missing(table: str, name: str, column: sa.Column) -> None:
    if context.is_offline_mode():
        op.add_column(table, column)
        return
    inspector = sa.inspect(op.get_bind())
    if table in inspector.get_table_names() and name not in {c["name"] for c in inspector.get_columns(table)}:
        op.add_column(table, column)


def upgrade() -> None:
    _add_missing(
        "public_registration_links", "assessment_questions",
        sa.Column("assessment_questions", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )
    _add_missing("inscriptions", "poste", sa.Column("poste", sa.String(length=100), nullable=True))
    _add_missing(
        "inscriptions", "date_inscription",
        sa.Column("date_inscription", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    _add_missing(
        "inscriptions", "reponses_positionnement",
        sa.Column("reponses_positionnement", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )
    _add_missing("inscriptions", "score_positionnement", sa.Column("score_positionnement", sa.Integer(), nullable=True))
    _add_missing("inscriptions", "niveau_initial", sa.Column("niveau_initial", sa.String(length=30), nullable=True))


def downgrade() -> None:
    if context.is_offline_mode():
        for table, name in (
            ("inscriptions", "niveau_initial"),
            ("inscriptions", "score_positionnement"),
            ("inscriptions", "reponses_positionnement"),
            ("inscriptions", "date_inscription"),
            ("inscriptions", "poste"),
            ("public_registration_links", "assessment_questions"),
        ):
            op.drop_column(table, name)
        return
    inspector = sa.inspect(op.get_bind())
    for table, name in (
        ("inscriptions", "niveau_initial"),
        ("inscriptions", "score_positionnement"),
        ("inscriptions", "reponses_positionnement"),
        ("inscriptions", "date_inscription"),
        ("inscriptions", "poste"),
        ("public_registration_links", "assessment_questions"),
    ):
        if table in inspector.get_table_names() and name in {c["name"] for c in inspector.get_columns(table)}:
            op.drop_column(table, name)
