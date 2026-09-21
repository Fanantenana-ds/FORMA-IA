"""
Tests des routes Backend POST /documents/tdr et POST /documents/offre
(contenu rédigé par le module IA).

Application FastAPI minimale (seul le router documents) + base SQLite en
mémoire : AUCUNE connexion à PostgreSQL, aucune donnée réelle touchée.

Exécution (sans le conftest.py, qui importe app.main et ouvre la base) :
    python -m pytest tests/unit/test_documents_route.py --noconftest -q
"""

import uuid

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.models.document  # noqa: F401  (enregistre les tables)
import app.models.formation  # noqa: F401
import app.models.historique_analyse  # noqa: F401
import app.models.user  # noqa: F401
from app.api.v1.endpoints import document as document_endpoints
from app.core.dependencies import get_current_user
from app.database import Base, get_db
from app.models.opportunite import Opportunite, SourceOpportunite
from app.services.backend_sync import offre_sync, tdr_sync

UUID_INCONNU = "00000000-0000-0000-0000-000000000000"


class FakeUser:
    def __init__(self, role):
        self.id = uuid.uuid4()
        self.role = role
        self.actif = True


@pytest.fixture
def env():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, autoflush=False)

    app = FastAPI()
    app.include_router(document_endpoints.router, prefix="/api/v1")

    def _get_db():
        db = session_factory()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = _get_db
    yield app, session_factory
    engine.dispose()


def client_as(app, role):
    user = FakeUser(role)
    app.dependency_overrides[get_current_user] = lambda: user
    return TestClient(app)


def creer_opportunite(session_factory) -> str:
    with session_factory() as db:
        opp = Opportunite(source=SourceOpportunite.TEXTE, contenu="AO de test")
        db.add(opp)
        db.commit()
        return str(opp.id)


# ============================================================
# Montage dans l'application réelle
# ============================================================

def test_le_router_de_l_application_monte_les_routes_documents():
    """
    Garde-fou : entre le 16/09 (commit daa5cd5) et le 21/09, router.py
    n'incluait plus document.router → toutes les routes /documents/...
    répondaient 404 dans l'application réelle, sans qu'aucun test de
    route isolée ne le voie.
    """
    from app.api.v1.router import api_router

    chemins = {route.path for route in api_router.routes}
    attendus = {
        "/documents/tdr",
        "/documents/offre",
        "/documents/attestations/{session_id}",
        "/documents/{document_id}",
        "/documents/{document_id}/valider",
        "/documents/{document_id}/export",
    }
    assert attendus <= chemins, f"Routes non montées : {attendus - chemins}"


def test_le_router_de_l_application_monte_analyse_et_les_routes_de_sync_ia():
    """
    Garde-fou : la route d'analyse avait été supprimée au commit e3cfb2d
    (14/09) sans que rien ne le signale ; les routes de synchronisation
    M3 / Préparation doivent aussi rester montées.
    """
    from app.api.v1.router import api_router

    chemins = {route.path for route in api_router.routes}
    attendus = {
        "/opportunites/{opportunite_id}/analyse",
        "/ia/offres/synchroniser",
        "/ia/preparation/synchroniser",
    }
    assert attendus <= chemins, f"Routes non montées : {attendus - chemins}"


# ============================================================
# POST /documents/tdr
# ============================================================

def test_tdr_sans_authentification(env):
    app, _ = env
    response = TestClient(app).post(
        "/api/v1/documents/tdr", json={"client": "C", "objectifs": "O"}
    )
    assert response.status_code == 401


def test_tdr_role_non_autorise(env):
    app, _ = env
    response = client_as(app, "COMPTABLE").post(
        "/api/v1/documents/tdr", json={"client": "C", "objectifs": "O"}
    )
    assert response.status_code == 403


def test_tdr_sans_contenu_garde_le_texte_par_defaut(env):
    app, _ = env
    response = client_as(app, "ASSISTANT").post(
        "/api/v1/documents/tdr",
        json={"client": "Todisoa Olivier", "objectifs": "Former 20 agents"},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["type"] == "TDR"
    assert data["statut_validation"] == "EN_ATTENTE"
    assert data["contenu"].startswith("TDR - Client: Todisoa Olivier")


def test_tdr_avec_contenu_ia_et_format_est_conserve(env):
    app, _ = env
    client = client_as(app, "DIRECTION")
    created = client.post(
        "/api/v1/documents/tdr",
        json={
            "client": "Ministère",
            "objectifs": "Maîtriser les LLM",
            "contenu": '{"titre": "TDR IA"}',
            "format_export": "DOCX",
        },
    )
    assert created.status_code == 201

    relu = client.get(f"/api/v1/documents/{created.json()['id']}").json()
    assert relu["contenu"] == '{"titre": "TDR IA"}'
    assert relu["format_export"] == "DOCX"


def test_tdr_opportunite_inconnue(env):
    app, _ = env
    response = client_as(app, "ASSISTANT").post(
        "/api/v1/documents/tdr",
        json={"client": "C", "objectifs": "O", "opportunite_id": UUID_INCONNU},
    )
    assert response.status_code == 404


def test_tdr_champs_obligatoires_vides_refuses(env):
    app, _ = env
    response = client_as(app, "ASSISTANT").post(
        "/api/v1/documents/tdr", json={"client": "", "objectifs": "O"}
    )
    assert response.status_code == 422


def test_tdr_payload_de_la_sync_ia_est_accepte(env):
    """Le payload exact de tdr_sync (avec champs inconnus) doit passer."""
    app, session_factory = env
    opp_id = creer_opportunite(session_factory)

    payload = tdr_sync._build_tdr_payload(
        {"client": "Ministère", "objectif_general": "Former 20 agents"},
        docx_filename="tdr.docx",
        pdf_filename=None,
        opportunite_id=opp_id,
    )
    response = client_as(app, "DIRECTION").post(
        "/api/v1/documents/tdr", json=payload
    )

    assert response.status_code == 201
    data = response.json()
    assert data["format_export"] == "DOCX"
    assert data["client"] == "Ministère"
    assert data["objectifs"] == "Former 20 agents"


# ============================================================
# POST /documents/offre
# ============================================================

def test_offre_avec_contenu_ia(env):
    app, session_factory = env
    opp_id = creer_opportunite(session_factory)

    response = client_as(app, "ASSISTANT").post(
        "/api/v1/documents/offre",
        json={
            "opportunite_id": opp_id,
            "montant": 2_280_000,
            "contenu": "OFFRE TECHNIQUE\n===============\nTitre : IA",
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert data["type"] == "OFFRE"
    assert data["contenu"] == "OFFRE TECHNIQUE\n===============\nTitre : IA"


def test_offre_sans_contenu_garde_le_texte_par_defaut(env):
    app, session_factory = env
    opp_id = creer_opportunite(session_factory)

    response = client_as(app, "ASSISTANT").post(
        "/api/v1/documents/offre",
        json={"opportunite_id": opp_id, "montant": 1000},
    )
    assert response.status_code == 201
    assert response.json()["contenu"].startswith("Offre technique et financière")


def test_offre_opportunite_inconnue(env):
    app, _ = env
    response = client_as(app, "ASSISTANT").post(
        "/api/v1/documents/offre", json={"opportunite_id": UUID_INCONNU}
    )
    assert response.status_code == 404


def test_offre_contenu_trop_long_refuse(env):
    app, session_factory = env
    opp_id = creer_opportunite(session_factory)

    response = client_as(app, "ASSISTANT").post(
        "/api/v1/documents/offre",
        json={"opportunite_id": opp_id, "contenu": "x" * 500_001},
    )
    assert response.status_code == 422


def test_offre_texte_construit_par_la_sync_ia_est_accepte(env):
    app, session_factory = env
    opp_id = creer_opportunite(session_factory)

    resultat_ia = {
        "offre_technique": {"reference": "ALT-OFF-TECH-2026-0001",
                            "modules": [{"titre": "Introduction"}]},
        "offre_financiere": {"recapitulatif": {"net_a_payer": 2_280_000}},
        "_review_id": "HITL-AM3-0001",
    }
    contenu = offre_sync.build_contenu(resultat_ia)

    response = client_as(app, "DIRECTION").post(
        "/api/v1/documents/offre",
        json={"opportunite_id": opp_id,
              "montant": offre_sync.extract_montant(
                  {"offre_financiere": resultat_ia["offre_financiere"]}),
              "contenu": contenu},
    )
    assert response.status_code == 201
    stocke = response.json()["contenu"]
    assert "OFFRE TECHNIQUE" in stocke and "ALT-OFF-TECH-2026-0001" in stocke
    assert "HITL" not in stocke                      # clé interne _review_id exclue
