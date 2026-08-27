def test_create_opportunite_role_non_autorise(client_role):
    client = client_role(role="FORMATEUR")
    response = client.post(
        "/api/v1/opportunites",
        json={
            "source": "TEXTE",
            "contenu": "Test opportunité",
        }
    )
    assert response.status_code == 403


def test_delete_opportunite_role_non_autorise(client_role):
    client = client_role(role="COMPTABLE")
    response = client.delete(
        "/api/v1/opportunites/16c6314c-9c24-4654-abb9-2df429a49937"
    )
    assert response.status_code == 403


def test_update_opportunite_role_non_autorise(client_role):
    client = client_role(role="FORMATEUR")
    response = client.put(
        "/api/v1/opportunites/16c6314c-9c24-4654-abb9-2df429a49937",
        json={
            "source": "TEXTE",
            "contenu": "Contenu modifié",
            "objet": "Objet modifié",
            "domaine": "IA",
        }
    )
    assert response.status_code == 403


def test_create_opportunite_role_autorise(client_role):
    client = client_role(role="ASSISTANT")
    response = client.post(
        "/api/v1/opportunites",
        json={
            "source": "TEXTE",
            "contenu": "Test opportunité",
        }
    )
    assert response.status_code == 201