import pytest
from uuid import uuid4

from fastapi import status


def assert_status_ok(
    response,
    expected_statuses=None,
):
    """
    Vérifie que la réponse HTTP est considérée comme valide.

    En cas de 422, affiche directement le détail Pydantic
    pour faciliter le diagnostic.
    """
    if expected_statuses is None:
        expected_statuses = [
            status.HTTP_200_OK,
            status.HTTP_201_CREATED,
        ]

    if response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY:
        print("\n❌ ERREUR DE VALIDATION Pydantic (422):")
        try:
            print(response.json())
        except Exception:
            print(response.text)

    assert response.status_code in expected_statuses, (
        f"\n❌ Statut HTTP inattendu : {response.status_code}\n"
        f"Réponse : {response.text}"
    )


# =============================================================================
# 1. HEALTH
# =============================================================================

def test_preparation_ia_health(client_ia):
    """
    Vérifie que le module Préparation IA est disponible.
    """
    response = client_ia.get("/api/v1/ia/preparation/health")

    assert_status_ok(response)

    data = response.json()

    assert isinstance(data, dict)
    assert data.get("success") is True


# =============================================================================
# 2. CALCULER BUDGET
# =============================================================================

def test_calculer_budget_ia(client_ia):
    payload = {
        "formateur_info": {
            "nom": "M. RANAIVOSOA S.",
            "tarif_journalier": 500000
        },
        "salle_info": {
            "nom": "Salle A",
            "tarif_journalier": 200000
        },
        "nb_jours": 3,
        "nb_participants": 10
    }
    response = client_ia.post("/api/v1/ia/preparation/calculer-budget", json=payload)
    assert_status_ok(response)


def test_generer_edt_ia(client_ia):
    payload = {
        "titre_formation": "Introduction à l'IA",
        "modules": [
            {"titre": "Introduction", "duree": "3h"},
            {"titre": "Apprentissage", "duree": "3h"}
        ],
        "dates": ["2026-10-01", "2026-10-02", "2026-10-03"]
    }
    response = client_ia.post("/api/v1/ia/preparation/generer-edt", json=payload)
    assert_status_ok(response)


def test_generer_complet_ia(client_ia):
    payload = {
        "offre_data": {
            "reference": "ALT-OFF-TECH-2026-0001",
            "titre": "Formation Python & FastAPI",
            "duree_jours": 3,
            "modules": [
                {"titre": "Introduction", "duree": "3h"}
            ]
        },
        "projet_info": {
            "client": "Client Test",
            "nb_participants": 10
        },
        "ressources": {
            "formateur": {"nom": "Formateur Test", "tarif_journalier": 400000},
            "salle": {"nom": "Salle Test", "tarif_journalier": 150000}
        }
    }
    response = client_ia.post("/api/v1/ia/preparation/generer-complet", json=payload)
    assert_status_ok(response)

# =============================================================================
# 5. SYNCHRONISER
# =============================================================================

def test_synchroniser_ia(client_ia):
    """
    Test : synchroniser une review inexistante doit retourner 422
    (ou créer une review d'abord).
    """
    payload = {
        "review_id": str(uuid4()),  # UUID aléatoire = inexistant
        "force": True
    }
    response = client_ia.post("/api/v1/ia/preparation/synchroniser", json=payload)

    # Un review_id inexistant DOIT retourner 422
    assert response.status_code == 422
    assert "introuvable" in response.json()["detail"]
