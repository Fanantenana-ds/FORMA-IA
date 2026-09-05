def test_creer_session_sans_auth(client):
    response = client.post(
        "/api/v1/sessions",
        json={
            "titre": "Formation PostgreSQL",
            "date_debut": "2026-10-01",
            "date_fin": "2026-10-03"
        }
    )
    assert response.status_code == 401


def test_creer_session_role_non_autorise(client_role):
    client = client_role(role="COMPTABLE")
    response = client.post(
        "/api/v1/sessions",
        json={
            "titre": "Formation PostgreSQL",
            "date_debut": "2026-10-01",
            "date_fin": "2026-10-03"
        }
    )
    assert response.status_code == 403


def test_creer_session_role_autorise(client_role):
    client = client_role(role="FORMATEUR")
    response = client.post(
        "/api/v1/sessions",
        json={
            "titre": "Formation PostgreSQL",
            "date_debut": "2026-10-01",
            "date_fin": "2026-10-03"
        }
    )
    assert response.status_code == 201
    data = response.json()
    assert data["titre"] == "Formation PostgreSQL"


def test_get_session_inexistante(client_authenticated):
    response = client_authenticated.get(
        "/api/v1/sessions/00000000-0000-0000-0000-000000000000"
    )
    assert response.status_code == 404
    
def test_ajouter_seance_session_inexistante(client_role):
    client = client_role(role="FORMATEUR")
    response = client.post(
        "/api/v1/sessions/00000000-0000-0000-0000-000000000000/seances",
        json={
            "date": "2026-10-01",
            "theme": "Introduction"
        }
    )
    assert response.status_code == 404


def test_creer_participant_role_autorise(client_role):
    client = client_role(role="ASSISTANT")
    response = client.post(
        "/api/v1/participants",
        json={
            "nom": "Todisoa",
            "email": "todisoa@gmail.com",
            "entreprise": "Anonyme SARL"
        }
    )
    assert response.status_code == 201
    data = response.json()
    assert data["nom"] == "Todisoa"


def test_enregistrer_presence_seance_inexistante(client_role):
    client = client_role(role="FORMATEUR")
    response = client.post(
        "/api/v1/sessions/seances/00000000-0000-0000-0000-000000000000/presences",
        json={
            "participant_id": "00000000-0000-0000-0000-000000000000",
            "statut": "PRESENT"
        }
    )
    assert response.status_code == 404


def test_flux_complet_session_seance_presence(client_role):
    client = client_role(role="FORMATEUR")


    session_resp = client.post(
        "/api/v1/sessions",
        json={
            "titre": "Formation Docker",
            "date_debut": "2026-11-01",
            "date_fin": "2026-11-02"
        }
    )
    assert session_resp.status_code == 201
    session_id = session_resp.json()["id"]


    seance_resp = client.post(
        f"/api/v1/sessions/{session_id}/seances",
        json={
            "date": "2026-11-01",
            "theme": "Introduction à Docker"
        }
    )
    print(seance_resp.json())
    assert seance_resp.status_code == 201
    seance_id = seance_resp.json()["id"]

    participant_resp = client.post(
        "/api/v1/participants",
        json={"nom": "ANDRIANOTAHINA", "email": "andrianotahina@gmail.com"}
    )
    assert participant_resp.status_code == 201
    participant_id = participant_resp.json()["id"]


    presence_resp = client.post(
        f"/api/v1/sessions/seances/{seance_id}/presences",
        json={
            "participant_id": participant_id,
            "statut": "PRESENT"
        }
    )
    print(presence_resp.json())
    assert presence_resp.status_code == 201
    data = presence_resp.json()
    assert data["statut"] == "PRESENT"
    assert data["source"] == "MANUEL"