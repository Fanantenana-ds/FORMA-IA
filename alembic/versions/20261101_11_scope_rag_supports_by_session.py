"""Scope RAG chunks to a training session and module."""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import context, op
from sqlalchemy.dialects import postgresql

revision: str = "20261101_11"
down_revision: str | None = "20261101_10"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    if context.is_offline_mode():
        op.add_column("knowledge_base", sa.Column("session_id", postgresql.UUID(as_uuid=True), nullable=True))
        op.add_column("knowledge_base", sa.Column("module", sa.String(length=200), nullable=True))
        op.create_index("ix_knowledge_base_session_id", "knowledge_base", ["session_id"])
        op.create_index("ix_knowledge_base_module", "knowledge_base", ["module"])
        return

    inspector = sa.inspect(op.get_bind())
    if "knowledge_base" not in inspector.get_table_names():
        return
    columns = {column["name"] for column in inspector.get_columns("knowledge_base")}
    if "session_id" not in columns:
        op.add_column("knowledge_base", sa.Column("session_id", postgresql.UUID(as_uuid=True), nullable=True))
    if "module" not in columns:
        op.add_column("knowledge_base", sa.Column("module", sa.String(length=200), nullable=True))
    indexes = {index["name"] for index in inspector.get_indexes("knowledge_base")}
    if "ix_knowledge_base_session_id" not in indexes:
        op.create_index("ix_knowledge_base_session_id", "knowledge_base", ["session_id"])
    if "ix_knowledge_base_module" not in indexes:
        op.create_index("ix_knowledge_base_module", "knowledge_base", ["module"])


def downgrade() -> None:
    if context.is_offline_mode():
        op.drop_index("ix_knowledge_base_module", table_name="knowledge_base")
        op.drop_index("ix_knowledge_base_session_id", table_name="knowledge_base")
        op.drop_column("knowledge_base", "module")
        op.drop_column("knowledge_base", "session_id")
        return

    inspector = sa.inspect(op.get_bind())
    if "knowledge_base" not in inspector.get_table_names():
        return
    indexes = {index["name"] for index in inspector.get_indexes("knowledge_base")}
    for name in ("ix_knowledge_base_module", "ix_knowledge_base_session_id"):
        if name in indexes:
            op.drop_index(name, table_name="knowledge_base")
    columns = {column["name"] for column in inspector.get_columns("knowledge_base")}
    for name in ("module", "session_id"):
        if name in columns:
            op.drop_column("knowledge_base", name)
