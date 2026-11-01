"""Bind trainer applications and assignments to their training session."""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import context, op
from sqlalchemy.dialects import postgresql

revision: str = "20261101_02"
down_revision: str | None = "20261101_01"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _drop_fk_to_users(table: str) -> None:
    inspector = sa.inspect(op.get_bind())
    for fk in inspector.get_foreign_keys(table):
        if "formateur_id" in (fk.get("constrained_columns") or []) and fk.get("referred_table") == "users":
            if fk.get("name"):
                op.drop_constraint(fk["name"], table, type_="foreignkey")


def upgrade() -> None:
    if context.is_offline_mode():
        op.add_column("candidats", sa.Column("session_id", postgresql.UUID(as_uuid=True), nullable=True))
        op.create_foreign_key("fk_candidats_session_id_sessions", "candidats", "sessions", ["session_id"], ["id"], ondelete="SET NULL")
        op.drop_constraint("sessions_formateur_id_fkey", "sessions", type_="foreignkey")
        op.drop_constraint("fk_seances_formateur_id_users", "seances", type_="foreignkey")
        op.create_foreign_key("fk_sessions_formateur_id_formateurs", "sessions", "formateurs", ["formateur_id"], ["id"], ondelete="SET NULL")
        op.create_foreign_key("fk_seances_formateur_id_formateurs", "seances", "formateurs", ["formateur_id"], ["id"], ondelete="SET NULL")
        return

    bind = op.get_bind()
    inspector = sa.inspect(bind)
    candidat_columns = {column["name"] for column in inspector.get_columns("candidats")}
    if "session_id" not in candidat_columns:
        op.add_column("candidats", sa.Column("session_id", postgresql.UUID(as_uuid=True), nullable=True))
    candidate_fks = inspector.get_foreign_keys("candidats")
    if not any(fk.get("constrained_columns") == ["session_id"] and fk.get("referred_table") == "sessions" for fk in candidate_fks):
        op.create_foreign_key("fk_candidats_session_id_sessions", "candidats", "sessions", ["session_id"], ["id"], ondelete="SET NULL")

    for table in ("sessions", "seances"):
        _drop_fk_to_users(table)
        inspector = sa.inspect(bind)
        fks = inspector.get_foreign_keys(table)
        has_formateur_fk = any(
            fk.get("constrained_columns") == ["formateur_id"] and fk.get("referred_table") == "formateurs"
            for fk in fks
        )
        if not has_formateur_fk:
            op.execute(sa.text(
                f"UPDATE {table} SET formateur_id = NULL "
                "WHERE formateur_id IS NOT NULL AND formateur_id NOT IN (SELECT id FROM formateurs)"
            ))
            constraint = f"fk_{table}_formateur_id_formateurs"
            op.create_foreign_key(constraint, table, "formateurs", ["formateur_id"], ["id"], ondelete="SET NULL")


def downgrade() -> None:
    bind = op.get_bind()
    if context.is_offline_mode():
        op.drop_constraint("fk_sessions_formateur_id_formateurs", "sessions", type_="foreignkey")
        op.drop_constraint("fk_seances_formateur_id_formateurs", "seances", type_="foreignkey")
        op.drop_constraint("fk_candidats_session_id_sessions", "candidats", type_="foreignkey")
        op.drop_column("candidats", "session_id")
        return

    for table in ("sessions", "seances"):
        for fk in sa.inspect(bind).get_foreign_keys(table):
            if "formateur_id" in (fk.get("constrained_columns") or []) and fk.get("referred_table") == "formateurs" and fk.get("name"):
                op.drop_constraint(fk["name"], table, type_="foreignkey")
        op.execute(sa.text(
            f"UPDATE {table} SET formateur_id = NULL "
            "WHERE formateur_id IS NOT NULL AND formateur_id NOT IN (SELECT id FROM users)"
        ))
        op.create_foreign_key(f"fk_{table}_formateur_id_users", table, "users", ["formateur_id"], ["id"], ondelete="SET NULL")

    for fk in sa.inspect(bind).get_foreign_keys("candidats"):
        if fk.get("constrained_columns") == ["session_id"] and fk.get("referred_table") == "sessions" and fk.get("name"):
            op.drop_constraint(fk["name"], "candidats", type_="foreignkey")
    if "session_id" in {column["name"] for column in sa.inspect(bind).get_columns("candidats")}:
        op.drop_column("candidats", "session_id")
