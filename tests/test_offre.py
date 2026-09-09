def test_generer_offre_sans_auth(client):
    response = client.post(
        "/api/v1/documents/offre",
        json={"opportunite_id": "00000000-0000-0000-0000-000000000000"}
    )
    assert response.status_code == 401


def test_generer_offre_role_non_autorise(client_role):
    client = client_role(role="COMPTABLE")
    response = client.post(
        "/api/v1/documents/offre",
        json={"opportunite_id": "00000000-0000-0000-0000-000000000000"}
    )
    assert response.status_code == 403


def test_generer_offre_opportunite_inexistante(client_role):
    client = client_role(role="ASSISTANT")
    response = client.post(
        "/api/v1/documents/offre",
        json={"opportunite_id": "00000000-0000-0000-0000-000000000000"}
    )
    assert response.status_code == 404


def test_generer_offre_role_autorise(client_role):
    client = client_role(role="ASSISTANT")

    # Créer une opportunité au préalable
    opportunite_resp = client.post(
        "/api/v1/opportunites",
        json={
            "source": "TEXTE",
            "contenu": "Appel d'offre formation Kubernetes pour 30 agents"
        }
    )
    assert opportunite_resp.status_code == 201
    opportunite_id = opportunite_resp.json()["id"]

    response = client.post(
        "/api/v1/documents/offre",
        json={
            "opportunite_id": opportunite_id,
            "montant": 15000000
        }
    )
    assert response.status_code == 201
    data = response.json()
    assert data["type"] == "OFFRE"
    assert data["statut_validation"] == "EN_ATTENTE"


def test_generer_offre_sans_montant(client_role):
    client = client_role(role="DIRECTION")

    opportunite_resp = client.post(
        "/api/v1/opportunites",
        json={
            "source": "TEXTE",
            "contenu": "Appel d'offre formation DevOps"
        }
    )
    opportunite_id = opportunite_resp.json()["id"]

    response = client.post(
        "/api/v1/documents/offre",
        json={"opportunite_id": opportunite_id}
    )
    assert response.status_code == 201