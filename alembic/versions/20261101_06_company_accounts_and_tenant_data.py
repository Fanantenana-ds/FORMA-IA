"""Add company ownership and link trainer profiles to login accounts."""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import context, op
from sqlalchemy.dialects import postgresql

revision: str = "20261101_06"
down_revision: str | None = "20261101_05"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TENANT_TABLES = (
    "sessions", "seances", "participants", "inscriptions", "presences",
    "opportunites", "formateurs", "candidats", "entretiens", "factures",
    "paiements", "relances", "documents", "offres", "historique_analyses",
    "knowledge_base", "public_registration_links", "public_assessment_attempts",
    "salles", "projets", "edt_sessions", "budgets_formation",
)


def upgrade() -> None:
    if context.is_offline_mode():
        op.drop_index("uq_kb_hash_collection_chunk", table_name="knowledge_base")
        op.add_column("users", sa.Column("owner_id", postgresql.UUID(as_uuid=True), nullable=True))
        op.create_index("ix_users_owner_id", "users", ["owner_id"], unique=False)
        for table in TENANT_TABLES:
            op.add_column(table, sa.Column("owner_id", postgresql.UUID(as_uuid=True), nullable=True))
            op.create_index(f"ix_{table}_owner_id", table, ["owner_id"], unique=False)
        op.execute("UPDATE users SET owner_id = id WHERE owner_id IS NULL AND role::text = 'DIRECTION'")
        op.execute("UPDATE users SET owner_id = (SELECT id FROM users WHERE role::text = 'DIRECTION' ORDER BY id LIMIT 1) WHERE owner_id IS NULL AND EXISTS (SELECT 1 FROM users WHERE role::text = 'DIRECTION')")
        for table in TENANT_TABLES:
            op.execute(f'UPDATE "{table}" SET owner_id = (SELECT id FROM users WHERE role::text = \'DIRECTION\' ORDER BY id LIMIT 1) WHERE owner_id IS NULL AND EXISTS (SELECT 1 FROM users WHERE role::text = \'DIRECTION\')')
        op.create_index("uq_kb_tenant_hash_collection_chunk", "knowledge_base", ["owner_id", "doc_hash", "collection", "chunk_index"], unique=True)
        op.add_column("formateurs", sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=True))
        op.create_index("ix_formateurs_user_id", "formateurs", ["user_id"], unique=True)
        op.create_foreign_key("fk_formateurs_user_id_users", "formateurs", "users", ["user_id"], ["id"], ondelete="SET NULL")
        op.create_foreign_key("fk_users_owner_id_users", "users", "users", ["owner_id"], ["id"], ondelete="SET NULL")
        return

    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    if "users" in tables and "owner_id" not in {c["name"] for c in inspector.get_columns("users")}:
        op.add_column("users", sa.Column("owner_id", postgresql.UUID(as_uuid=True), nullable=True))
    inspector = sa.inspect(bind)
    if "users" in tables:
        indexes = {item["name"] for item in inspector.get_indexes("users")}
        if "ix_users_owner_id" not in indexes:
            op.create_index("ix_users_owner_id", "users", ["owner_id"], unique=False)
    for table in TENANT_TABLES:
        if table in tables and "owner_id" not in {c["name"] for c in inspector.get_columns(table)}:
            op.add_column(table, sa.Column("owner_id", postgresql.UUID(as_uuid=True), nullable=True))
            inspector = sa.inspect(bind)
        if table in tables:
            indexes = {item["name"] for item in sa.inspect(bind).get_indexes(table)}
            if f"ix_{table}_owner_id" not in indexes:
                op.create_index(f"ix_{table}_owner_id", table, ["owner_id"], unique=False)

    if "formateurs" in tables and "user_id" not in {c["name"] for c in inspector.get_columns("formateurs")}:
        op.add_column("formateurs", sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=True))
        inspector = sa.inspect(bind)
    if "formateurs" in tables:
        indexes = {item["name"] for item in inspector.get_indexes("formateurs")}
        if "ix_formateurs_user_id" not in indexes:
            op.create_index("ix_formateurs_user_id", "formateurs", ["user_id"], unique=True)
        foreign_keys = {item.get("name") for item in inspector.get_foreign_keys("formateurs")}
        if "fk_formateurs_user_id_users" not in foreign_keys:
            op.create_foreign_key("fk_formateurs_user_id_users", "formateurs", "users", ["user_id"], ["id"], ondelete="SET NULL")

    if "users" in tables:
        user_foreign_keys = {item.get("name") for item in sa.inspect(bind).get_foreign_keys("users")}
        if "fk_users_owner_id_users" not in user_foreign_keys:
            op.create_foreign_key("fk_users_owner_id_users", "users", "users", ["owner_id"], ["id"], ondelete="SET NULL")
        # Each existing director becomes the owner of their company. Legacy
        # records are assigned to the first director so development data stays visible.
        bind.execute(sa.text("UPDATE users SET owner_id = id WHERE owner_id IS NULL AND role::text = 'DIRECTION'"))
        owner_id = bind.execute(sa.text("SELECT id FROM users WHERE role::text = 'DIRECTION' ORDER BY id LIMIT 1")).scalar()
        if owner_id is not None:
            # Existing assistants/comptables were created before the tenant
            # relationship existed. Keep their access in the same legacy
            # company as its records instead of treating each as a tenant.
            bind.execute(
                sa.text("UPDATE users SET owner_id = :owner_id WHERE owner_id IS NULL"),
                {"owner_id": owner_id},
            )
            for table in TENANT_TABLES:
                if table in tables and "owner_id" in {c["name"] for c in sa.inspect(bind).get_columns(table)}:
                    bind.execute(sa.text(f'UPDATE "{table}" SET owner_id = :owner_id WHERE owner_id IS NULL'), {"owner_id": owner_id})

    if "knowledge_base" in tables:
        kb_indexes = {item["name"] for item in sa.inspect(bind).get_indexes("knowledge_base")}
        if "uq_kb_hash_collection_chunk" in kb_indexes:
            op.drop_index("uq_kb_hash_collection_chunk", table_name="knowledge_base")
        if "uq_kb_tenant_hash_collection_chunk" not in kb_indexes:
            op.create_index(
                "uq_kb_tenant_hash_collection_chunk", "knowledge_base",
                ["owner_id", "doc_hash", "collection", "chunk_index"], unique=True,
            )


def downgrade() -> None:
    if context.is_offline_mode():
        op.drop_index("uq_kb_tenant_hash_collection_chunk", table_name="knowledge_base")
        op.create_index("uq_kb_hash_collection_chunk", "knowledge_base", ["doc_hash", "collection", "chunk_index"], unique=True)
        op.drop_index("ix_formateurs_user_id", table_name="formateurs")
        op.drop_column("formateurs", "user_id")
        for table in reversed(TENANT_TABLES):
            op.drop_index(f"ix_{table}_owner_id", table_name=table)
            op.drop_column(table, "owner_id")
        op.drop_index("ix_users_owner_id", table_name="users")
        op.drop_column("users", "owner_id")
        return
    inspector = sa.inspect(op.get_bind())
    if "knowledge_base" in inspector.get_table_names():
        indexes = {item["name"] for item in inspector.get_indexes("knowledge_base")}
        if "uq_kb_tenant_hash_collection_chunk" in indexes:
            op.drop_index("uq_kb_tenant_hash_collection_chunk", table_name="knowledge_base")
        if "uq_kb_hash_collection_chunk" not in indexes:
            op.create_index("uq_kb_hash_collection_chunk", "knowledge_base", ["doc_hash", "collection", "chunk_index"], unique=True)
    if "formateurs" in inspector.get_table_names():
        indexes = {item["name"] for item in inspector.get_indexes("formateurs")}
        if "ix_formateurs_user_id" in indexes:
            op.drop_index("ix_formateurs_user_id", table_name="formateurs")
        if "user_id" in {c["name"] for c in inspector.get_columns("formateurs")}:
            foreign_keys = {item.get("name") for item in inspector.get_foreign_keys("formateurs")}
            if "fk_formateurs_user_id_users" in foreign_keys:
                op.drop_constraint("fk_formateurs_user_id_users", "formateurs", type_="foreignkey")
            op.drop_column("formateurs", "user_id")
    inspector = sa.inspect(op.get_bind())
    if "users" in inspector.get_table_names():
        foreign_keys = {item.get("name") for item in inspector.get_foreign_keys("users")}
        if "fk_users_owner_id_users" in foreign_keys:
            op.drop_constraint("fk_users_owner_id_users", "users", type_="foreignkey")
    for table in reversed(TENANT_TABLES):
        inspector = sa.inspect(op.get_bind())
        if table in inspector.get_table_names() and "owner_id" in {c["name"] for c in inspector.get_columns(table)}:
            indexes = {item["name"] for item in inspector.get_indexes(table)}
            if f"ix_{table}_owner_id" in indexes:
                op.drop_index(f"ix_{table}_owner_id", table_name=table)
            op.drop_column(table, "owner_id")
    inspector = sa.inspect(op.get_bind())
    if "users" in inspector.get_table_names() and "owner_id" in {c["name"] for c in inspector.get_columns("users")}:
        indexes = {item["name"] for item in inspector.get_indexes("users")}
        if "ix_users_owner_id" in indexes:
            op.drop_index("ix_users_owner_id", table_name="users")
        op.drop_column("users", "owner_id")
