def test_get_statistiques_sans_auth(client):
    response = client.get("/api/v1/dashboard/statistiques")
    assert response.status_code == 401


def test_get_statistiques_role_non_autorise(client_role):
    client = client_role(role="FORMATEUR")
    response = client.get("/api/v1/dashboard/statistiques")
    assert response.status_code == 403


def test_get_statistiques_role_autorise(client_role):
    client = client_role(role="DIRECTION")
    response = client.get("/api/v1/dashboard/statistiques")

    assert response.status_code == 200
    data = response.json()

    assert isinstance(data["session_realisees"], int)
    assert isinstance(data["participant"], int)
    assert isinstance(data["taux_presence"], float)
    assert isinstance(data["opportunite_par_domaine"], dict)
    assert data["chiffre_affaires_facture"] == 0.0
    assert data["chiffre_affaires_encaisse"] == 0.0
    assert data["session_realisees"] >= 0
    assert 0.0 <= data["taux_presence"] <= 100.0


def test_get_statistiques_reflete_opportunites_par_domaine(client_role):
    client = client_role(role="DIRECTION")

    avant = client.get("/api/v1/dashboard/statistiques").json()
    total_ia_avant = avant["opportunite_par_domaine"].get("IA", 0)

    creation = client.post(
        "/api/v1/opportunites",
        json={
            "source": "TEXTE",
            "contenu": "Formation sur les modèles de langage",
            "domaine": "IA"
        }
    )
    assert creation.status_code == 201

    apres = client.get("/api/v1/dashboard/statistiques").json()
    total_ia_apres = apres["opportunite_par_domaine"].get("IA", 0)

    assert total_ia_apres == total_ia_avant + 1