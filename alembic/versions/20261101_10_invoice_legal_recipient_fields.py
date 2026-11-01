"""Store recipient legal details for professional invoice documents."""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import context, op

revision: str = "20261101_10"
down_revision: str | None = "20261101_09"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


_COLUMNS = {
    "client_adresse": sa.String(length=300),
    "client_siret": sa.String(length=32),
    "client_rcs": sa.String(length=120),
    "client_tva": sa.String(length=32),
}


def upgrade() -> None:
    if context.is_offline_mode():
        for name, column_type in _COLUMNS.items():
            op.add_column("factures", sa.Column(name, column_type, nullable=True))
        return
    inspector = sa.inspect(op.get_bind())
    if "factures" not in inspector.get_table_names():
        return
    present = {item["name"] for item in inspector.get_columns("factures")}
    for name, column_type in _COLUMNS.items():
        if name not in present:
            op.add_column("factures", sa.Column(name, column_type, nullable=True))


def downgrade() -> None:
    if context.is_offline_mode():
        for name in reversed(tuple(_COLUMNS)):
            op.drop_column("factures", name)
        return
    inspector = sa.inspect(op.get_bind())
    if "factures" not in inspector.get_table_names():
        return
    present = {item["name"] for item in inspector.get_columns("factures")}
    for name in reversed(tuple(_COLUMNS)):
        if name in present:
            op.drop_column("factures", name)
