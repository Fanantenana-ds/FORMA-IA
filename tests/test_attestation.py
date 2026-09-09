def test_generer_attestation_sans_auth(client):
    response = client.post(
        "/api/v1/documents/attestations/00000000-0000-0000-0000-000000000000"
    )
    assert response.status_code == 401

def test_generer_attestation_role_non_autorise(client_role):
    client = client_role(role="COMPTABLE")
    response = client.post(
        "/api/v1/documents/attestations/00000000-0000-0000-0000-000000000000"
    )
    assert response.status_code == 403

def test_generer_attestations_session_inexistante(client_role):
    client = client_role(role="FORMATEUR")
    response = client.post(
        "/api/v1/documents/attestations/00000000-0000-0000-0000-000000000000"
    )
    assert response.status_code == 404

def test_generer_attestations_flux_complet(client_role):
    client = client_role(role="FORMATEUR")

    # 1. Créer une session
    session_resp = client.post(
        "/api/v1/sessions",
        json={
            "titre": "Formation Kubernetes",
            "date_debut": "2026-12-01",
            "date_fin": "2026-12-02"
        }
    )
    assert session_resp.status_code == 201
    session_id = session_resp.json()["id"]

    # 2. Ajouter une séance
    seance_resp = client.post(
        f"/api/v1/sessions/{session_id}/seances",
        json={"date": "2026-12-01", "theme": "Introduction"}
    )
    assert seance_resp.status_code == 201
    seance_id = seance_resp.json()["id"]

    # 3. Créer deux participants
    p1_resp = client.post(
        "/api/v1/participants",
        json={"nom": "Rakoto Jean", "email": "jean@example.com"}
    )
    assert p1_resp.status_code == 201
    p1_id = p1_resp.json()["id"]

    p2_resp = client.post(
        "/api/v1/participants",
        json={"nom": "Rasoa Marie", "email": "marie@example.com"}
    )
    assert p2_resp.status_code == 201
    p2_id = p2_resp.json()["id"]

    # 4. Enregistrer les présences : p1 présent, p2 absent
    presence1_resp = client.post(
        f"/api/v1/sessions/seances/{seance_id}/presences",
        json={"participant_id": p1_id, "statut": "PRESENT"}
    )
    assert presence1_resp.status_code == 201

    presence2_resp = client.post(
        f"/api/v1/sessions/seances/{seance_id}/presences",
        json={"participant_id": p2_id, "statut": "ABSENT"}
    )
    assert presence2_resp.status_code == 201

    # 5. Générer les attestations en lot
    attestations_resp = client.post(f"/api/v1/documents/attestations/{session_id}")
    assert attestations_resp.status_code == 201
    data = attestations_resp.json()

    # Seul le participant présent doit avoir une attestation
    assert len(data) == 1
    assert data[0]["participant_id"] == p1_id
    assert data[0]["type"] == "ATTESTATION"
    assert data[0]["numero_unique"] is not None
    assert data[0]["statut_validation"] == "EN_ATTENTE"


def test_generer_attestations_idempotent(client_role):
    client = client_role(role="FORMATEUR")

    session_resp = client.post(
        "/api/v1/sessions",
        json={
            "titre": "Formation Ansible",
            "date_debut": "2026-12-10",
            "date_fin": "2026-12-11"
        }
    )
    session_id = session_resp.json()["id"]

    seance_resp = client.post(
        f"/api/v1/sessions/{session_id}/seances",
        json={"date": "2026-12-10", "theme": "Bases"}
    )
    seance_id = seance_resp.json()["id"]

    participant_resp = client.post(
        "/api/v1/participants",
        json={"nom": "Rabe Paul", "email": "paul@example.com"}
    )
    participant_id = participant_resp.json()["id"]

    client.post(
        f"/api/v1/sessions/seances/{seance_id}/presences",
        json={"participant_id": participant_id, "statut": "PRESENT"}
    )

    # Premier appel : crée l'attestation
    resp1 = client.post(f"/api/v1/documents/attestations/{session_id}")
    assert resp1.status_code == 201
    assert len(resp1.json()) == 1
    numero_1 = resp1.json()[0]["numero_unique"]

    # Second appel : ne doit pas dupliquer
    resp2 = client.post(f"/api/v1/documents/attestations/{session_id}")
    assert resp2.status_code == 201
    assert len(resp2.json()) == 1
    assert resp2.json()[0]["numero_unique"] == numero_1