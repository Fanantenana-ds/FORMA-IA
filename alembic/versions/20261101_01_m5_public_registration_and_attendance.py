"""M5 session fields, public links, candidate contacts and late attendance."""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import context, op
from sqlalchemy.dialects import postgresql

revision: str = "20261101_01"
down_revision: str | None = "0001_initial"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    if context.is_offline_mode():
        # Offline SQL generation cannot inspect the live catalog; emit the
        # complete canonical migration in this mode.
        op.execute("ALTER TYPE statutpresence ADD VALUE IF NOT EXISTS 'RETARD'")
        op.alter_column("participants", "email", existing_type=sa.String(length=30), type_=sa.String(length=200), existing_nullable=True)
        op.alter_column("participants", "entreprise", existing_type=sa.String(length=30), type_=sa.String(length=100), existing_nullable=True)
        for table, column in [
            ("sessions", sa.Column("formation_code", sa.String(50), nullable=True)),
            ("sessions", sa.Column("lieu", sa.String(200), nullable=True)),
            ("sessions", sa.Column("nb_participants_max", sa.Integer(), nullable=True)),
            ("seances", sa.Column("heure_debut", sa.String(5), nullable=True)),
            ("seances", sa.Column("heure_fin", sa.String(5), nullable=True)),
            ("seances", sa.Column("formateur_id", postgresql.UUID(as_uuid=True), nullable=True)),
            ("participants", sa.Column("prenom", sa.String(50), nullable=True)),
            ("presences", sa.Column("heure_arrivee", sa.String(5), nullable=True)),
            ("presences", sa.Column("motif_absence", sa.String(500), nullable=True)),
            ("candidats", sa.Column("prenom", sa.String(100), nullable=True)),
            ("candidats", sa.Column("email", sa.String(200), nullable=True)),
            ("candidats", sa.Column("telephone", sa.String(30), nullable=True)),
            ("candidats", sa.Column("cv_filename", sa.String(255), nullable=True)),
            ("candidats", sa.Column("cv_path", sa.String(500), nullable=True)),
        ]:
            op.add_column(table, column)
        op.create_foreign_key("fk_seances_formateur_id_users", "seances", "users", ["formateur_id"], ["id"], ondelete="SET NULL")
        op.create_table(
            "public_registration_links",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
            sa.Column("token", sa.String(96), nullable=False, unique=True),
            sa.Column("kind", sa.String(20), nullable=False),
            sa.Column("session_id", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("date_creation", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.ForeignKeyConstraint(["session_id"], ["sessions.id"], ondelete="CASCADE"),
        )
        op.create_index("ix_public_registration_links_token", "public_registration_links", ["token"], unique=True)
        return

    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())
    if bind.dialect.name == "postgresql":
        op.execute("ALTER TYPE statutpresence ADD VALUE IF NOT EXISTS 'RETARD'")

    # The development app historically ran Base.metadata.create_all() on import.
    # Some databases therefore already contain part (or all) of this revision
    # while their alembic_version table is empty. Make this revision resumable.
    participant_columns = {column["name"]: column for column in inspector.get_columns("participants")}
    for name, target_length in (("email", 200), ("entreprise", 100)):
        column = participant_columns.get(name)
        current_type = getattr(column["type"], "length", None) if column else None
        if column and current_type != target_length:
            op.alter_column(
                "participants", name,
                existing_type=column["type"],
                type_=sa.String(length=target_length),
                existing_nullable=column["nullable"],
            )

    for table, column in [
        ("sessions", sa.Column("formation_code", sa.String(50), nullable=True)),
        ("sessions", sa.Column("lieu", sa.String(200), nullable=True)),
        ("sessions", sa.Column("nb_participants_max", sa.Integer(), nullable=True)),
        ("seances", sa.Column("heure_debut", sa.String(5), nullable=True)),
        ("seances", sa.Column("heure_fin", sa.String(5), nullable=True)),
        ("seances", sa.Column("formateur_id", postgresql.UUID(as_uuid=True), nullable=True)),
        ("participants", sa.Column("prenom", sa.String(50), nullable=True)),
        ("presences", sa.Column("heure_arrivee", sa.String(5), nullable=True)),
        ("presences", sa.Column("motif_absence", sa.String(500), nullable=True)),
        ("candidats", sa.Column("prenom", sa.String(100), nullable=True)),
        ("candidats", sa.Column("email", sa.String(200), nullable=True)),
        ("candidats", sa.Column("telephone", sa.String(30), nullable=True)),
        ("candidats", sa.Column("cv_filename", sa.String(255), nullable=True)),
        ("candidats", sa.Column("cv_path", sa.String(500), nullable=True)),
    ]:
        present = {item["name"] for item in inspector.get_columns(table)}
        if column.name not in present:
            op.add_column(table, column)

    has_trainer_fk = any(
        fk.get("constrained_columns") == ["formateur_id"]
        and fk.get("referred_table") == "users"
        and fk.get("referred_columns") == ["id"]
        for fk in inspector.get_foreign_keys("seances")
    )
    if not has_trainer_fk:
        op.create_foreign_key(
            "fk_seances_formateur_id_users", "seances", "users", ["formateur_id"], ["id"], ondelete="SET NULL"
        )

    if "public_registration_links" not in tables:
        op.create_table(
            "public_registration_links",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
            sa.Column("token", sa.String(96), nullable=False, unique=True),
            sa.Column("kind", sa.String(20), nullable=False),
            sa.Column("session_id", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("date_creation", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.ForeignKeyConstraint(["session_id"], ["sessions.id"], ondelete="CASCADE"),
        )
        inspector = sa.inspect(bind)
    indexes = {index["name"] for index in inspector.get_indexes("public_registration_links")}
    if "ix_public_registration_links_token" not in indexes:
        op.create_index("ix_public_registration_links_token", "public_registration_links", ["token"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_public_registration_links_token", table_name="public_registration_links")
    op.drop_table("public_registration_links")
    op.drop_constraint("fk_seances_formateur_id_users", "seances", type_="foreignkey")
    op.alter_column("participants", "email", existing_type=sa.String(length=200), type_=sa.String(length=30), existing_nullable=True)
    op.alter_column("participants", "entreprise", existing_type=sa.String(length=100), type_=sa.String(length=30), existing_nullable=True)
    for table, column in [
        ("sessions", "formation_code"), ("sessions", "lieu"), ("sessions", "nb_participants_max"),
        ("seances", "heure_debut"), ("seances", "heure_fin"), ("seances", "formateur_id"),
        ("participants", "prenom"), ("presences", "heure_arrivee"), ("presences", "motif_absence"),
        ("candidats", "prenom"), ("candidats", "email"), ("candidats", "telephone"), ("candidats", "cv_filename"), ("candidats", "cv_path"),
    ]:
        op.drop_column(table, column)
