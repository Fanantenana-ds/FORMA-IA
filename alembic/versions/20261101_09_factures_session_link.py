"""Associate invoices with completed training sessions."""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import context, op
from sqlalchemy.dialects import postgresql

revision: str = "20261101_09"
down_revision: str | None = "20261101_08"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    column = sa.Column("session_id", postgresql.UUID(as_uuid=True), nullable=True)
    if context.is_offline_mode():
        op.add_column("factures", column)
        op.create_foreign_key("fk_factures_session_id_sessions", "factures", "sessions", ["session_id"], ["id"], ondelete="SET NULL")
        op.create_index("ix_factures_session_id", "factures", ["session_id"], unique=False)
        return
    inspector = sa.inspect(op.get_bind())
    if "factures" not in inspector.get_table_names():
        return
    columns = {item["name"] for item in inspector.get_columns("factures")}
    if "session_id" not in columns:
        op.add_column("factures", column)
    foreign_keys = {item.get("name") for item in inspector.get_foreign_keys("factures")}
    if "fk_factures_session_id_sessions" not in foreign_keys:
        op.create_foreign_key("fk_factures_session_id_sessions", "factures", "sessions", ["session_id"], ["id"], ondelete="SET NULL")
    indexes = {item["name"] for item in inspector.get_indexes("factures")}
    if "ix_factures_session_id" not in indexes:
        op.create_index("ix_factures_session_id", "factures", ["session_id"], unique=False)


def downgrade() -> None:
    if context.is_offline_mode():
        op.drop_index("ix_factures_session_id", table_name="factures")
        op.drop_constraint("fk_factures_session_id_sessions", "factures", type_="foreignkey")
        op.drop_column("factures", "session_id")
        return
    inspector = sa.inspect(op.get_bind())
    if "factures" not in inspector.get_table_names():
        return
    indexes = {item["name"] for item in inspector.get_indexes("factures")}
    if "ix_factures_session_id" in indexes:
        op.drop_index("ix_factures_session_id", table_name="factures")
    foreign_keys = {item.get("name") for item in inspector.get_foreign_keys("factures")}
    if "fk_factures_session_id_sessions" in foreign_keys:
        op.drop_constraint("fk_factures_session_id_sessions", "factures", type_="foreignkey")
    columns = {item["name"] for item in inspector.get_columns("factures")}
    if "session_id" in columns:
        op.drop_column("factures", "session_id")
