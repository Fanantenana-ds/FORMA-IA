from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

TOKEN = ""
AUTH_HEADERS = {"Authorization": f"Bearer {TOKEN}"}


# tests/test_analyse.py

def test_analyse_sans_auth(client):
    response = client.post(
        "/api/v1/opportunites/16c6314c-9c24-4654-abb9-2df429a49937/analyse"
    )
    assert response.status_code == 401


def test_analyse_opportunite_inexistante(client_authenticated):
    response = client_authenticated.post(
        "/api/v1/opportunites/00000000-9c24-4654-abb9-2df429a49937/analyse"
    )
    assert response.status_code == 404


def test_analyse_avec_auth_et_opportunite_existante(client_authenticated):
    response = client_authenticated.post(
        "/api/v1/opportunites/16c6314c-9c24-4654-abb9-2df429a49937/analyse"
    )
    assert response.status_code == 200
    data = response.json()
    assert "score_pertinence" in data