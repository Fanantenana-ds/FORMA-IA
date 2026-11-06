"""Routes du profil utilisateur : mise à jour et photo synchronisée."""

from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from app.api.v1.endpoints import auth
from app.core.dependencies import get_current_user
from app.database import get_db
from app.models.historique_analyse import HistoriqueAnalyse as _HistoriqueAnalyse
from app.models.user import RoleEnum
from app.models.user_profile_photo import UserProfilePhoto
from app.services.auth_service import AuthService


class FakeDb:
    def __init__(self):
        self.saved = []
        self.commits = 0
        self.photos = {}

    def add(self, item):
        self.saved.append(item)
        if isinstance(item, UserProfilePhoto):
            self.photos[item.user_id] = item

    def delete(self, item):
        self.photos.pop(item.user_id, None)

    def query(self, _model):
        return FakeQuery(self)

    def commit(self):
        self.commits += 1


class FakeUser:
    def __init__(self):
        self.id = uuid4()
        self.nom = "Formateur Test"
        self.email = "formateur@example.test"
        self.role = RoleEnum.FORMATEUR


class FakeQuery:
    def __init__(self, db):
        self.db = db

    def filter(self, *_criteria):
        return self

    def first(self):
        return next(iter(self.db.photos.values()), None)


def make_client(user=None, db=None):
    app = FastAPI()
    app.include_router(auth.router, prefix="/api/v1")
    app.dependency_overrides[get_current_user] = lambda: user or FakeUser()
    app.dependency_overrides[get_db] = lambda: db or FakeDb()
    return TestClient(app)


def test_photo_profil_upload_read_and_delete():
    user = FakeUser()
    db = FakeDb()
    client = make_client(user, db)
    jpeg = b"\xff\xd8\xff\x01test\xff\xd9"

    uploaded = client.put(
        "/api/v1/auth/me/photo",
        files={"fichier": ("profil.jpg", jpeg, "image/jpeg")},
    )
    assert uploaded.status_code == 200
    assert uploaded.json()["success"] is True
    assert db.photos[user.id].contenu == jpeg
    assert db.commits == 1

    fetched = client.get("/api/v1/auth/me/photo")
    assert fetched.status_code == 200
    assert fetched.content == jpeg
    assert fetched.headers["content-type"] == "image/jpeg"
    assert fetched.headers["cache-control"] == "private, no-store"

    deleted = client.delete("/api/v1/auth/me/photo")
    assert deleted.status_code == 200
    assert not db.photos
    assert db.commits == 2
    assert client.get("/api/v1/auth/me/photo").status_code == 404


@pytest.mark.parametrize(
    ("filename", "content", "media_type", "expected_status"),
    [
        ("profil.png", b"\x89PNG\r\n\x1a\n", "image/png", 415),
        ("profil.jpg", b"pas une image", "image/jpeg", 422),
        ("profil.jpg", b"\xff\xd8\xff" + b"x" * (auth.TAILLE_MAX_PHOTO_PROFIL - 4) + b"\xff\xd9", "image/jpeg", 413),
    ],
    ids=["png-refuse", "jpeg-invalide", "photo-superieure-a-1mo"],
)
def test_photo_profil_rejette_format_invalide_ou_fichier_trop_lourd(filename, content, media_type, expected_status):
    response = make_client().put(
        "/api/v1/auth/me/photo",
        files={"fichier": (filename, content, media_type)},
    )
    assert response.status_code == expected_status


def test_get_photo_profil_sans_photo_retourne_404():
    response = make_client().get("/api/v1/auth/me/photo")
    assert response.status_code == 404


def test_update_own_profile_saves_only_name_and_email(monkeypatch):
    user = FakeUser()

    class FakeAuthService:
        def __init__(self, _db):
            pass

        def mettre_a_jour_profil(self, current_user, data):
            for field, value in data.model_dump(exclude_unset=True).items():
                setattr(current_user, field, value)
            return current_user

    monkeypatch.setattr(auth, "AuthService", FakeAuthService)
    response = make_client(user).patch(
        "/api/v1/auth/me",
        json={"nom": "Nouveau nom", "email": "nouveau@example.com"},
    )
    assert response.status_code == 200
    assert response.json()["nom"] == "Nouveau nom"
    assert response.json()["email"] == "nouveau@example.com"
    assert response.json()["role"] == "FORMATEUR"


def test_service_refuse_email_deja_utilise():
    user = SimpleNamespace(id=uuid4(), nom="Nom", email="ancien@example.test")
    duplicate = SimpleNamespace(id=uuid4())
    service = AuthService(object())
    service.user_repository = SimpleNamespace(
        find_by_email=lambda _email: duplicate,
        save=lambda _user: pytest.fail("Le compte ne doit pas être enregistré"),
    )

    from app.schemas.user import UserProfileUpdate

    with pytest.raises(HTTPException) as exc:
        service.mettre_a_jour_profil(user, UserProfileUpdate(email="deja-utilise@example.com"))
    assert exc.value.status_code == 400
