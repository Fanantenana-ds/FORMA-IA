"""creation des tables sessions, seances, participants, inscriptions, presences

Revision ID: bd5a74464171
Revises: f8a371d13349
Create Date: 2026-09-02 13:26:56.330334

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'bd5a74464171'
down_revision: Union[str, None] = 'f8a371d13349'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "sessions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("titre", sa.String(255), nullable=False),
        sa.Column("client", sa.String(255), nullable=True),
        sa.Column("date_debut", sa.Date(), nullable=False),
        sa.Column("date_fin", sa.Date(), nullable=True),
        sa.Column("formateur_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("date_creation", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )

    op.create_table(
        "participants",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("nom", sa.String(255), nullable=False),
        sa.Column("email", sa.String(255), nullable=True),
        sa.Column("entreprise", sa.String(255), nullable=True),
    )

    op.create_table(
        "seances",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("session_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("sessions.id"), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("duree", sa.String(50), nullable=True),
        sa.Column("theme", sa.String(255), nullable=True),
    )

    op.create_table(
        "inscriptions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("session_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("sessions.id"), nullable=False),
        sa.Column("participant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("participants.id"), nullable=False),
    )

    op.create_table(
        "presences",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("seance_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("seances.id"), nullable=False),
        sa.Column("participant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("participants.id"), nullable=False),
        sa.Column(
            "statut",
            sa.Enum("PRESENT", "ABSENT", "EXCUSE", name="statutpresence"),
            nullable=False
        ),
        sa.Column(
            "source",
            sa.Enum("MANUEL", "GOOGLE_FORMS", name="sourcepresence"),
            nullable=False,
            server_default="MANUEL"
        ),
    )


def downgrade() -> None:
    op.drop_table("presences")
    op.execute("DROP TYPE IF EXISTS statutpresence")
    op.execute("DROP TYPE IF EXISTS sourcepresence")
    op.drop_table("inscriptions")
    op.drop_table("seances")
    op.drop_table("participants")
    op.drop_table("sessions")