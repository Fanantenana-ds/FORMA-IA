import pytest


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
    # Ne dépend pas des données déjà présentes en base (avant : == 0.0, ce qui
    # supposait une base sans aucune facture) : le calcul est vérifié plus bas,
    # de façon relative, par test_get_statistiques_reflete_le_chiffre_d_affaires_facture
    assert data["chiffre_affaires_facture"] >= 0.0
    assert data["chiffre_affaires_encaisse"] >= 0.0
    assert data["session_realisees"] >= 0
    assert 0.0 <= data["taux_presence"] <= 100.0


def test_get_statistiques_reflete_le_chiffre_d_affaires_facture(client_role):
    client = client_role(role="DIRECTION")

    avant = client.get("/api/v1/dashboard/statistiques").json()
    ca_avant = avant["chiffre_affaires_facture"]

    creation = client.post(
        "/api/v1/factures",
        json={"client": "Client de test", "montant": 1000},
    )
    assert creation.status_code == 201

    apres = client.get("/api/v1/dashboard/statistiques").json()
    assert apres["chiffre_affaires_facture"] == pytest.approx(ca_avant + 1000.0)


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


def test_montant_impaye_ne_soustrait_pas_les_paiements_des_factures_payees(
    client_role,
):
    """
    Régression : l'ancien calcul soustrayait TOUS les paiements encaissés
    (y compris ceux sur factures PAYEES) aux TTC des factures NON payées.
    Scénario minimal qui exposait le bug :
      - Facture A : TTC 1 000 000, PAYEE, soldée
      - Facture B : TTC 1 000 000, EMISE, non payée
      → montant_impaye attendu = 1 000 000 (reste dû sur B)
      → ancien bug retournait 0
    """
    client = client_role(role="DIRECTION")

    # --- État initial
    avant = client.get("/api/v1/dashboard/statistiques").json()
    impaye_avant = avant["montant_impaye"]

    # --- Facture A : 1 000 000 HT + 20% TVA = 1 200 000 TTC, PAYEE
    facture_a = client.post(
        "/api/v1/factures",
        json={
            "client": "Client A",
            "montant": 1_000_000,
            "tva_taux": 20.0,
        },
    )
    assert facture_a.status_code == 201
    facture_a_id = facture_a.json()["id"]

    # Paiement intégral → statut passe à PAYEE
    paiement = client.post(
        f"/api/v1/factures/{facture_a_id}/paiements",
        json={
            "montant": 1_200_000,
            "date": "2026-09-30",
        },
    )
    assert paiement.status_code == 201

    # --- Facture B : 1 000 000 HT + 20% TVA = 1 200 000 TTC, EMISE
    facture_b = client.post(
        "/api/v1/factures",
        json={
            "client": "Client B",
            "montant": 1_000_000,
            "tva_taux": 20.0,
        },
    )
    assert facture_b.status_code == 201

    # --- Vérification
    apres = client.get("/api/v1/dashboard/statistiques").json()
    impaye_apres = apres["montant_impaye"]

    # Facture A soldée → n'ajoute rien
    # Facture B non payée → ajoute 1 200 000 TTC
    assert impaye_apres == pytest.approx(impaye_avant + 1_200_000.0, abs=0.01), (
        f"montant_impaye attendu {impaye_avant + 1_200_000}, "
        f"obtenu {impaye_apres}"
    )


def test_montant_impaye_avec_paiement_partiel(client_role):
    """
    Cas partiel : une facture partiellement payée ne compte que son reste dû.
    """
    client = client_role(role="DIRECTION")

    avant = client.get("/api/v1/dashboard/statistiques").json()
    impaye_avant = avant["montant_impaye"]

    # Facture : 1 000 000 HT + 20% TVA = 1 200 000 TTC
    creation = client.post(
        "/api/v1/factures",
        json={
            "client": "Client partiel",
            "montant": 1_000_000,
            "tva_taux": 20.0,
        },
    )
    assert creation.status_code == 201
    facture_id = creation.json()["id"]

    # Paiement partiel : 500 000 (reste 700 000 dû)
    paiement = client.post(
        f"/api/v1/factures/{facture_id}/paiements",
        json={
            "montant": 500_000,
            "date": "2026-09-30",
        },
    )
    assert paiement.status_code == 201

    apres = client.get("/api/v1/dashboard/statistiques").json()
    impaye_apres = apres["montant_impaye"]

    # Reste dû sur cette facture = 1 200 000 - 500 000 = 700 000
    assert impaye_apres == pytest.approx(impaye_avant + 700_000.0, abs=0.01)