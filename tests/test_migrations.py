import os
import subprocess
import sys

import pytest
from sqlalchemy import create_engine, text

URL = os.getenv("MIGRATION_TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(
    not URL, reason="MIGRATION_TEST_DATABASE_URL non défini (PostgreSQL requis)"
)


def _alembic(*args):
    env = {**os.environ, "DATABASE_URL": URL}
    return subprocess.run(
        [sys.executable, "-m", "alembic", *args],
        env=env, capture_output=True, text=True,
    )


@pytest.fixture
def base_vide():
    engine = create_engine(URL)
    with engine.begin() as conn:
        conn.execute(text("DROP SCHEMA public CASCADE"))
        conn.execute(text("CREATE SCHEMA public"))
    engine.dispose()


def test_upgrade_head_depuis_base_vide(base_vide):
    r = _alembic("upgrade", "head")
    assert r.returncode == 0, r.stderr[-3000:]


def test_migrations_alignees_sur_les_modeles(base_vide):
    assert _alembic("upgrade", "head").returncode == 0
    r = _alembic("check")
    assert r.returncode == 0, (r.stdout + r.stderr)[-3000:]
