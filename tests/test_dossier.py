import uuid


def _creer_opportunite(client):
    response = client.post("/api/v1/opportunites", json={"source": "TEXTE", "contenu": "Formation IA pour une administration"})
    assert response.status_code == 201
    return response.json()["id"]


def test_etat_dossier_sans_auth(client):
    response = client.get(f"/api/v1/dossiers/{uuid.uuid4()}/etat")
    assert response.status_code == 401


def test_etat_dossier_role_non_autorise(client_role):
    client = client_role(role="FORMATEUR")
    response = client.get(f"/api/v1/dossiers/{uuid.uuid4()}/etat")
    assert response.status_code == 403


def test_etat_dossier_introuvable(client_role):
    client = client_role(role="DIRECTION")
    response = client.get(f"/api/v1/dossiers/{uuid.uuid4()}/etat")
    assert response.status_code == 404


def test_etat_dossier_nouvelle_opportunite(client_role):
    client = client_role(role="DIRECTION")
    opportunite_id = _creer_opportunite(client)

    response = client.get(f"/api/v1/dossiers/{opportunite_id}/etat")
    assert response.status_code == 200
    data = response.json()

    cles = [e["cle"] for e in data["etapes"]]
    assert cles[:5] == ["opportunite", "tdr", "offre_technique", "offre_financiere", "preparation"]
    assert data["etapes"][0]["etat"] == "done"
    assert data["session_id"] is None
    assert data["prochaine_action"]["cle"] == "tdr"
    assert data["progression"] == {"faites": 1, "total": len(data["etapes"])}
