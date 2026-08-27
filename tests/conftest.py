import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.models.core.dependencies import get_current_user
from app.models.user import User

class FakeUser:
    def __init__(self, id="1f12722d-7108-4fc8-9de3-ffb258195f12", role="DIRECTION", actif=True):
        self.id = id
        self.role = role
        self.actif = actif

@pytest.fixture
def client_authenticated():
    def override_get_current_user():
        return FakeUser()

    app.dependency_overrides[get_current_user] = override_get_current_user
    yield TestClient(app)
    app.dependency_overrides.pop(get_current_user, None)

@pytest.fixture
def client():
    return TestClient(app)

@pytest.fixture
def client_role():
    """Fabrique un client authentifié avec un rôle et un statut actif donnés."""
    def _make(role="DIRECTION", actif=True):
        fake_user = FakeUser(role=role, actif=actif)

        def override_get_current_user():
            return fake_user

        app.dependency_overrides[get_current_user] = override_get_current_user
        return TestClient(app)

    yield _make
    app.dependency_overrides.pop(get_current_user, None)