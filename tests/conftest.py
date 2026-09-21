import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session as DbSession

from app.main import app
from app.core.dependencies import get_current_user
from app.database import engine, get_db
from app.models.user import User, RoleEnum

FAKE_USER_ID = "1f12722d-7108-4fc8-9de3-ffb258195f12"

class FakeUser:
    def __init__(self, id=FAKE_USER_ID, role="DIRECTION", actif=True):
        self.id = id
        self.role = role
        self.actif = actif


@pytest.fixture(autouse=True)
def _analyse_sans_llm(monkeypatch):
    """
    L'analyse IA d'une opportunité appelle Groq (extraction) si la clé est
    configurée. Les tests ne doivent jamais consommer de quota : extraction LLM
    coupée par défaut, les tests qui en ont besoin la réactivent avec un faux LLM.
    """
    monkeypatch.setenv("ANALYSE_USE_LLM", "false")


@pytest.fixture
def db_isolee():
    """
    Exécute le test dans une transaction ANNULÉE à la fin : aucune ligne de test
    n'atteint la base PostgreSQL (avant : opportunités, documents, sessions… de
    test s'accumulaient dans « formaia »).

    - Chaque requête reçoit une session en SAVEPOINT : les db.commit() des
      services restent possibles, mais ne sont jamais validés pour de bon.
    - Un utilisateur factice RÉEL est créé dans cette transaction : les clés
      étrangères vers users.id (ex. documents.valide_par) sont ainsi respectées.
    """
    connection = engine.connect()
    transaction = connection.begin()

    def override_get_db():
        db = DbSession(
            bind=connection,
            join_transaction_mode="create_savepoint",
            autoflush=False,
        )
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db

    with DbSession(bind=connection, join_transaction_mode="create_savepoint") as db:
        db.add(User(
            id=uuid.UUID(FAKE_USER_ID),
            nom="Utilisateur de test",
            email="utilisateur-de-test@example.invalid",
            password="!",
            role=RoleEnum.DIRECTION,
            actif=True,
        ))
        db.commit()

    yield

    app.dependency_overrides.pop(get_db, None)
    transaction.rollback()
    connection.close()


@pytest.fixture
def client_authenticated(db_isolee):
    def override_get_current_user():
        return FakeUser()

    app.dependency_overrides[get_current_user] = override_get_current_user
    yield TestClient(app)
    app.dependency_overrides.pop(get_current_user, None)

@pytest.fixture
def client(db_isolee):
    return TestClient(app)

@pytest.fixture
def client_role(db_isolee):
    """Fabrique un client authentifié avec un rôle et un statut actif donnés."""
    def _make(role="DIRECTION", actif=True):
        fake_user = FakeUser(role=role, actif=actif)

        def override_get_current_user():
            return fake_user

        app.dependency_overrides[get_current_user] = override_get_current_user
        return TestClient(app)

    yield _make
    app.dependency_overrides.pop(get_current_user, None)
