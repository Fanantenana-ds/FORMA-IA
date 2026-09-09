def test_export_sans_auth(client):
    response = client.get(
        "/api/v1/documents/00000000-0000-0000-0000-000000000000/export?format=PDF"
    )
    assert response.status_code == 401


def test_export_document_inexistant(client_authenticated):
    response = client_authenticated.get(
        "/api/v1/documents/00000000-0000-0000-0000-000000000000/export?format=PDF"
    )
    assert response.status_code == 404


def test_export_pdf(client_role):
    client = client_role(role="ASSISTANT")

    creation = client.post(
        "/api/v1/documents/tdr",
        json={
            "client": "Client Export Test",
            "objectifs": "Former 15 agents sur Kubernetes"
        }
    )
    assert creation.status_code == 201
    document_id = creation.json()["id"]

    response = client.get(f"/api/v1/documents/{document_id}/export?format=PDF")

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert "attachment" in response.headers["content-disposition"]
    assert response.content.startswith(b"%PDF")


def test_export_word(client_role):
    client = client_role(role="ASSISTANT")

    creation = client.post(
        "/api/v1/documents/tdr",
        json={
            "client": "Client Export Test 2",
            "objectifs": "Former 10 agents sur Docker"
        }
    )
    assert creation.status_code == 201
    document_id = creation.json()["id"]

    response = client.get(f"/api/v1/documents/{document_id}/export?format=DOCX")

    assert response.status_code == 200
    assert response.headers["content-type"] == (
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    )
    assert "attachment" in response.headers["content-disposition"]
    # Un fichier .docx est une archive ZIP, signature "PK"
    assert response.content.startswith(b"PK")


def test_export_met_a_jour_format_export(client_role):
    client = client_role(role="ASSISTANT")

    creation = client.post(
        "/api/v1/documents/tdr",
        json={
            "client": "Client Export Test 3",
            "objectifs": "Former 5 agents sur Ansible"
        }
    )
    document_id = creation.json()["id"]

    client.get(f"/api/v1/documents/{document_id}/export?format=DOCX")

    # Vérifie que le document reflète le dernier format exporté
    get_resp = client.get(f"/api/v1/documents/{document_id}")
    assert get_resp.status_code == 200
    assert get_resp.json()["format_export"] == "DOCX"