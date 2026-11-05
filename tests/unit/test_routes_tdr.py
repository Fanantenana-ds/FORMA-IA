# ============================================================
# TESTS — app/api/v1/routes_tdr.py (M2)
# ============================================================
# Aucun appel LLM/Backend réel : l'orchestrateur module-level (routes_tdr.
# orchestrator) et les fonctions de fetch sont doublés. EXPORTS_DIR redirigé
# vers un dossier temporaire (aucun fichier réel touché).
# ============================================================

import asyncio
from uuid import UUID

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import app.services.tdr.tdr_document_generator as tdr_gen_module
from app.api.v1 import routes_tdr
from app.api.v1.endpoints import formation_ia
from app.core.tenant_context import set_tenant_id
from app.services.hitl import hitl_helper
from app.services.backend_sync.opportunity_fetcher import opportunity_to_brief
from app.utils import security
from app.utils.security import verify_api_key


@pytest.fixture(autouse=True)
def exports_dir_temporaire(monkeypatch, tmp_path):
    monkeypatch.setattr(tdr_gen_module, "get_tenant_exports_dir", lambda: tmp_path)
    monkeypatch.setattr(routes_tdr, "get_tenant_exports_dir", lambda: tmp_path)


@pytest.fixture
def client():
    app = FastAPI()
    app.include_router(routes_tdr.router)
    app.include_router(formation_ia.router)
    app.dependency_overrides[verify_api_key] = lambda: None
    return TestClient(app)


def _async(fn):
    async def wrapper(*args, **kwargs):
        return fn(*args, **kwargs)
    return wrapper


BRIEF = {
    "client": "Ministère de la Santé",
    "objectifs": "Former 50 agents à l'IA médicale",
    "public": "Agents de santé",
    "duree": "5 jours",
}


# ---- POST /ia/tdr/generer ----

def test_generer_tdr_success(client, monkeypatch):
    monkeypatch.setattr(
        routes_tdr.orchestrator, "generate",
        _async(lambda brief: {
            "success": True,
            "data": {"titre": "TDR Formation IA"},
            "files": {"docx": "tdr.docx", "pdf": "tdr.pdf"},
        }),
    )
    resp = client.post("/ia/tdr/generer", json=BRIEF)
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert body["files"]["docx"] == "tdr.docx"


def test_revue_tdr_creee_par_route_est_visible_dans_liste_hitl_du_meme_tenant(
    client, monkeypatch, tmp_path
):
    tenant_id = UUID("11111111-1111-4111-8111-111111111111")
    monkeypatch.setattr(hitl_helper, "STORAGE_PATH", tmp_path / "hitl_reviews.json")

    def faux_get_current_user(request, credential, db):
        set_tenant_id(tenant_id)
        return object()

    monkeypatch.setattr(security, "get_current_user", faux_get_current_user)
    client.app.dependency_overrides.pop(verify_api_key, None)
    client.app.dependency_overrides[security.get_db] = lambda: None

    async def generate(brief):
        data = {
            "success": True,
            "data": {"titre": "TDR formation IA", "formateur_nom": "À désigner"},
            "files": {"docx": "tdr.docx", "pdf": "tdr.pdf"},
            "_inputs": {"brief": brief},
        }
        review_id = hitl_helper.create_review(
            "agent_m2_tdr", data, "TDR formation IA", criticity="critical"
        )
        return {
            "success": True,
            "data": data["data"],
            "files": data["files"],
            "_review_id": review_id,
            "_review_status": "pending_review",
        }

    monkeypatch.setattr(routes_tdr.orchestrator, "generate", generate)

    generated = client.post("/ia/tdr/generer", json=BRIEF)
    assert generated.status_code == 200
    review_id = generated.json()["review_id"]

    pending = client.get("/ia/formations/pending-reviews")
    assert pending.status_code == 200
    assert any(
        review["review_id"] == review_id
        for review in pending.json()["reviews"]
    )


def test_brief_tdr_extrait_organisme_et_ne_prend_pas_enum_source_pour_client():
    brief = opportunity_to_brief({
        "id": "opportunity-1",
        "source": "URL",
        "objet": "Formation en intelligence artificielle",
        "contenu": "Résumé de l’avis | Organisme : Fonds d’Intervention pour le Développement | Type : AO | Lien : https://fid.mg/avis",
    })
    assert brief["client"] == "Fonds d’Intervention pour le Développement"

    sans_organisme = opportunity_to_brief({
        "source": "TEXTE",
        "objet": "Formation en intelligence artificielle",
        "contenu": "Texte de l’avis sans organisme explicite",
    })
    assert sans_organisme["client"] == ""


def test_generer_tdr_echec_orchestrateur(client, monkeypatch):
    monkeypatch.setattr(
        routes_tdr.orchestrator, "generate",
        _async(lambda brief: {"success": False, "error": "TDRService indisponible"}),
    )
    resp = client.post("/ia/tdr/generer", json=BRIEF)
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is False
    assert body["error"] == "TDRService indisponible"


def test_generer_tdr_exception_renvoie_500(client, monkeypatch):
    async def echoue(brief):
        raise RuntimeError("Groq indisponible")

    monkeypatch.setattr(routes_tdr.orchestrator, "generate", echoue)
    resp = client.post("/ia/tdr/generer", json=BRIEF)
    assert resp.status_code == 500


def test_generer_tdr_champs_obligatoires_manquants(client):
    resp = client.post("/ia/tdr/generer", json={"client": "x"})
    assert resp.status_code == 422


# ---- GET /ia/tdr/from-opportunite/{id} ----

def test_from_opportunite_success(client, monkeypatch):
    monkeypatch.setattr(
        routes_tdr, "fetch_opportunite_by_id",
        _async(lambda opp_id: {"id": opp_id, "objet": "Formation IA"}),
    )
    monkeypatch.setattr(
        routes_tdr, "opportunity_to_brief",
        lambda opp: {"client": "x", "objectifs": opp["objet"]},
    )
    resp = client.get("/ia/tdr/from-opportunite/abc-123")
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert body["brief"]["objectifs"] == "Formation IA"


def test_from_opportunite_introuvable(client, monkeypatch):
    monkeypatch.setattr(routes_tdr, "fetch_opportunite_by_id", _async(lambda opp_id: None))
    resp = client.get("/ia/tdr/from-opportunite/inexistant")
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is False
    assert "introuvable" in body["error"]


def test_from_opportunite_exception_renvoie_500(client, monkeypatch):
    async def echoue(opp_id):
        raise RuntimeError("Backend indisponible")

    monkeypatch.setattr(routes_tdr, "fetch_opportunite_by_id", echoue)
    resp = client.get("/ia/tdr/from-opportunite/abc-123")
    assert resp.status_code == 500


# ---- GET /ia/tdr/opportunites-disponibles ----

def test_opportunites_disponibles_success(client, monkeypatch):
    monkeypatch.setattr(
        routes_tdr, "fetch_opportunites_list",
        _async(lambda limit: [{"id": "1"}, {"id": "2"}]),
    )
    resp = client.get("/ia/tdr/opportunites-disponibles")
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert body["total"] == 2


def test_opportunites_disponibles_exception_renvoie_200_avec_erreur(client, monkeypatch):
    async def echoue(limit):
        raise RuntimeError("Backend indisponible")

    monkeypatch.setattr(routes_tdr, "fetch_opportunites_list", echoue)
    resp = client.get("/ia/tdr/opportunites-disponibles")
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is False
    assert body["data"] == []


def test_opportunites_disponibles_limit_hors_bornes(client):
    resp = client.get("/ia/tdr/opportunites-disponibles?limit=101")
    assert resp.status_code == 422


# ---- GET /ia/tdr/download/{filename} ----

def test_download_nom_fichier_invalide(client):
    resp = client.get("/ia/tdr/download/..%2F..%2Fsecret.docx")
    assert resp.status_code in (400, 404)  # normalisé par le routeur selon l'encodage


def test_download_fichier_introuvable(client):
    resp = client.get("/ia/tdr/download/inexistant.docx")
    assert resp.status_code == 404


def test_download_docx_success(client, tmp_path):
    (tmp_path / "tdr_test.docx").write_bytes(b"contenu factice")
    resp = client.get("/ia/tdr/download/tdr_test.docx")
    assert resp.status_code == 200
    assert "wordprocessingml" in resp.headers["content-type"]


def test_download_pdf_success(client, tmp_path):
    (tmp_path / "tdr_test.pdf").write_bytes(b"%PDF-1.4 contenu factice")
    resp = client.get("/ia/tdr/download/tdr_test.pdf")
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "application/pdf"


# ---- GET /ia/tdr/list ----

def test_list_tdr_dossier_absent(client, monkeypatch, tmp_path):
    dossier_absent = tmp_path / "n_existe_pas"
    monkeypatch.setattr(routes_tdr, "get_tenant_exports_dir", lambda: dossier_absent)
    resp = client.get("/ia/tdr/list")
    assert resp.status_code == 200
    body = resp.json()
    assert body["data"] == []
    assert body["total"] == 0


def test_list_tdr_avec_fichiers(client, monkeypatch, tmp_path):
    (tmp_path / "tdr_a.docx").write_bytes(b"a")
    (tmp_path / "tdr_b.pdf").write_bytes(b"b")
    (tmp_path / "ignore.txt").write_bytes(b"c")  # extension non listée
    resp = client.get("/ia/tdr/list")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 2
    noms = {f["name"] for f in body["data"]}
    assert noms == {"tdr_a.docx", "tdr_b.pdf"}
