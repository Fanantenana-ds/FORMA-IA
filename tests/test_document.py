def test_generer_tdr_sans_auth(client):
    response = client.post(
        "/api/v1/documents/tdr",
        json={
            "client": "Todisoa Olivier",
            "objectifs": "Former 20 agents sur PostgreSQL",
        }
    )
    assert response.status_code == 401

def test_generer_tdr_role_non_autorise(client_role):
    client = client_role(role="COMPTABLE")
    response = client.post(
        "/api/v1/documents/tdr",
        json = {
            "client": "Todisoa Olivier",
            "objectifs": "Former 20 agents sur PostgreSQL"
        }
    )
    assert response.status_code == 403

def test_generer_tdr_role_autorise(client_role):
    client = client_role(role="ASSISTANT")
    response = client.post(
        "/api/v1/documents/tdr",
        json = {
            "client": "Todisoa Olivier",
            "objectifs": "Former 20 agents sur PostgreSQL"
        }
    )
    assert response.status_code == 201
    data = response.json()
    assert data["type"] == "TDR"
    assert data["statut_validation"] == "EN_ATTENTE"

def test_valider_document_role_non_autorise(client_role):
    creation_client = client_role(role="ASSISTANT")
    creation = creation_client.post(
        "/api/v1/documents/tdr",
        json = {
            "client": "Todisoa Olivier",
            "objectifs": "Former 20 agents sur PostgreSQL"
        }
    )
    document_id = creation.json()["id"]

    validation_client = client_role(role="ASSISTANT")
    response = validation_client.post(
        f"/api/v1/documents/{document_id}/valider",
        json = {
            "approuve": True
        }
    )
    assert response.status_code == 403

def test_valider_document_role_autorise(client_role):
    creation_client = client_role(role="DIRECTION")
    creation = creation_client.post(
        "/api/v1/documents/tdr",
        json = {
            "client": "Todisoa Olivier",
            "objectifs": "Former 20 agents sur PostgreSQL"
        }
    )
    document_id = creation.json()["id"]

    validation_client = client_role(role="DIRECTION")
    response = validation_client.post(
        f"/api/v1/documents/{document_id}/valider",
        json={
            "approuve": True
        }
    )
    assert response.status_code == 200
    data = response.json()
    assert data["statut_validation"] == "VALIDE"



def test_valider_document_inexistant(client_role):
    client = client_role(role="DIRECTION")
    response = client.post(
        "/api/v1/documents/00000000-0000-0000-0000-000000000000/valider",
        json={
            "approuve": True
        }
    )
    assert response.status_code == 404