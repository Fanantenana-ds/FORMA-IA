"""Persist a distinct assessment attempt for each public link visitor."""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import context, op
from sqlalchemy.dialects import postgresql

revision: str = "20261101_05"
down_revision: str | None = "20261101_04"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    if context.is_offline_mode():
        op.create_table(
            "public_assessment_attempts",
            sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("token", sa.String(length=96), nullable=False),
            sa.Column("link_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("questions", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
            sa.Column("date_creation", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
            sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
            sa.ForeignKeyConstraint(["link_id"], ["public_registration_links.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("token"),
        )
        op.create_index("ix_public_assessment_attempts_link_id", "public_assessment_attempts", ["link_id"], unique=False)
        return

    inspector = sa.inspect(op.get_bind())
    if "public_assessment_attempts" not in inspector.get_table_names():
        op.create_table(
            "public_assessment_attempts",
            sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("token", sa.String(length=96), nullable=False),
            sa.Column("link_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("questions", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
            sa.Column("date_creation", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
            sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
            sa.ForeignKeyConstraint(["link_id"], ["public_registration_links.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("token"),
        )
        inspector = sa.inspect(op.get_bind())
    indexes = {item["name"] for item in inspector.get_indexes("public_assessment_attempts")}
    if "ix_public_assessment_attempts_link_id" not in indexes:
        op.create_index("ix_public_assessment_attempts_link_id", "public_assessment_attempts", ["link_id"], unique=False)


def downgrade() -> None:
    if context.is_offline_mode():
        op.drop_index("ix_public_assessment_attempts_link_id", table_name="public_assessment_attempts")
        op.drop_table("public_assessment_attempts")
        return
    inspector = sa.inspect(op.get_bind())
    if "public_assessment_attempts" in inspector.get_table_names():
        indexes = {item["name"] for item in inspector.get_indexes("public_assessment_attempts")}
        if "ix_public_assessment_attempts_link_id" in indexes:
            op.drop_index("ix_public_assessment_attempts_link_id", table_name="public_assessment_attempts")
        op.drop_table("public_assessment_attempts")
