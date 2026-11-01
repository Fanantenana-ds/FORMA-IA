"""Link each training session to the accepted opportunity and its TDR."""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import context, op
from sqlalchemy.dialects import postgresql

revision: str = "20261101_07"
down_revision: str | None = "20261101_06"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    if context.is_offline_mode():
        op.add_column("sessions", sa.Column("opportunite_id", postgresql.UUID(as_uuid=True), nullable=True))
        op.create_foreign_key(
            "fk_sessions_opportunite_id_opportunites", "sessions", "opportunites",
            ["opportunite_id"], ["id"], ondelete="SET NULL",
        )
        op.create_index("ix_sessions_opportunite_id", "sessions", ["opportunite_id"], unique=False)
        return

    inspector = sa.inspect(op.get_bind())
    columns = {column["name"] for column in inspector.get_columns("sessions")}
    if "opportunite_id" not in columns:
        op.add_column("sessions", sa.Column("opportunite_id", postgresql.UUID(as_uuid=True), nullable=True))
    constraints = {item.get("name") for item in inspector.get_foreign_keys("sessions")}
    if "fk_sessions_opportunite_id_opportunites" not in constraints:
        op.create_foreign_key(
            "fk_sessions_opportunite_id_opportunites", "sessions", "opportunites",
            ["opportunite_id"], ["id"], ondelete="SET NULL",
        )
    indexes = {item["name"] for item in inspector.get_indexes("sessions")}
    if "ix_sessions_opportunite_id" not in indexes:
        op.create_index("ix_sessions_opportunite_id", "sessions", ["opportunite_id"], unique=False)


def downgrade() -> None:
    if context.is_offline_mode():
        op.drop_index("ix_sessions_opportunite_id", table_name="sessions")
        op.drop_constraint("fk_sessions_opportunite_id_opportunites", "sessions", type_="foreignkey")
        op.drop_column("sessions", "opportunite_id")
        return

    inspector = sa.inspect(op.get_bind())
    if "sessions" not in inspector.get_table_names():
        return
    indexes = {item["name"] for item in inspector.get_indexes("sessions")}
    if "ix_sessions_opportunite_id" in indexes:
        op.drop_index("ix_sessions_opportunite_id", table_name="sessions")
    constraints = {item.get("name") for item in inspector.get_foreign_keys("sessions")}
    if "fk_sessions_opportunite_id_opportunites" in constraints:
        op.drop_constraint("fk_sessions_opportunite_id_opportunites", "sessions", type_="foreignkey")
    columns = {column["name"] for column in inspector.get_columns("sessions")}
    if "opportunite_id" in columns:
        op.drop_column("sessions", "opportunite_id")
