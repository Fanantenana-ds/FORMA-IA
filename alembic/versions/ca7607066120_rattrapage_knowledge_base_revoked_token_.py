"""rattrapage knowledge_base revoked_token participants_email

Revision ID: ca7607066120
Revises: 6af3872fceaf
Create Date: 2026-10-19 15:29:50.474718

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'ca7607066120'
down_revision: Union[str, None] = '6af3872fceaf'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has(table: str) -> bool:
    return sa.inspect(op.get_bind()).has_table(table)


def upgrade() -> None:
    # Tables jusque-là créées par create_all, sans migration : sans effet si elles existent déjà.
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    if not _has("knowledge_base"):
        op.create_table(
            "knowledge_base",
            sa.Column("id", sa.UUID(), primary_key=True),
            sa.Column("collection", sa.String(30), nullable=False),
            sa.Column("doc_hash", sa.String(64)),
            sa.Column("fichier", sa.String(500)),
            sa.Column("formation_code", sa.String(100)),
            sa.Column("formation_titre", sa.String(255)),
            sa.Column("domaine", sa.String(100)),
            sa.Column("annee", sa.Integer()),
            sa.Column("type_support", sa.String(20)),
            sa.Column("page_debut", sa.Integer()),
            sa.Column("page_fin", sa.Integer()),
            sa.Column("chunk_index", sa.Integer()),
            sa.Column("contenu", sa.Text(), nullable=False),
            sa.Column("embedding", Vector(1024), nullable=False),
            sa.Column("modele_embed", sa.String(50), nullable=False),
            sa.Column("meta", postgresql.JSONB()),
            sa.Column("created_at", sa.TIMESTAMP(), server_default=sa.text("now()")),
        )
        for col in ("collection", "doc_hash", "formation_code"):
            op.create_index(f"ix_knowledge_base_{col}", "knowledge_base", [col])

    if not _has("revoked_token"):
        op.create_table(
            "revoked_token",
            sa.Column("id", sa.UUID(), primary_key=True),
            sa.Column("jti", sa.String(), nullable=False),
            sa.Column("user_id", sa.UUID(), sa.ForeignKey("users.id"), nullable=False),
            sa.Column("expire_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=False),
        )
        op.create_index("ix_revoked_token_jti", "revoked_token", ["jti"], unique=True)

    op.alter_column(
        "participants", "email",
        existing_type=sa.String(30), type_=sa.String(255), existing_nullable=True,
    )


def downgrade() -> None:
    raise NotImplementedError("rattrapage : pas de retour arrière")