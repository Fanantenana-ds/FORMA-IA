"""Store authenticated users' profile photos."""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import context, op
from sqlalchemy.dialects import postgresql

revision: str = "20261107_01"
down_revision: str | None = "20261101_11"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    if context.is_offline_mode():
        op.create_table(
            "user_profile_photos",
            sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("contenu", sa.LargeBinary(), nullable=False),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("user_id"),
        )
        return

    tables = set(sa.inspect(op.get_bind()).get_table_names())
    if "users" not in tables or "user_profile_photos" in tables:
        return
    op.create_table(
        "user_profile_photos",
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("contenu", sa.LargeBinary(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("user_id"),
    )


def downgrade() -> None:
    if context.is_offline_mode():
        op.drop_table("user_profile_photos")
        return

    if "user_profile_photos" in sa.inspect(op.get_bind()).get_table_names():
        op.drop_table("user_profile_photos")
