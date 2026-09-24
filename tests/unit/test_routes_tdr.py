# ============================================================
# TESTS — app/api/v1/routes_tdr.py (M2)
# ============================================================
# Aucun appel LLM/Backend réel : l'orchestrateur module-level (routes_tdr.
# orchestrator) et les fonctions de fetch sont doublés. EXPORTS_DIR redirigé
# vers un dossier temporaire (aucun fichier réel touché).
# ============================================================

import asyncio

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.v1 import routes_tdr


@pytest.fixture(autouse=True)
def exports_dir_temporaire(monkeypatch, tmp_path):
    monkeypatch.setattr(routes_tdr, "EXPORTS_DIR", tmp_path)


@pytest.fixture
def client():
    app = FastAPI()
    app.include_router(routes_tdr.router)
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

def test_list_tdr_dossier_absent(client, tmp_path):
    dossier_absent = tmp_path / "n_existe_pas"
    import app.api.v1.routes_tdr as module
    module.EXPORTS_DIR = dossier_absent
    resp = client.get("/ia/tdr/list")
    assert resp.status_code == 200
    body = resp.json()
    assert body["data"] == []
    assert body["total"] == 0


def test_list_tdr_avec_fichiers(client, tmp_path):
    (tmp_path / "tdr_a.docx").write_bytes(b"a")
    (tmp_path / "tdr_b.pdf").write_bytes(b"b")
    (tmp_path / "ignore.txt").write_bytes(b"c")  # extension non listée
    resp = client.get("/ia/tdr/list")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 2
    noms = {f["name"] for f in body["data"]}
    assert noms == {"tdr_a.docx", "tdr_b.pdf"}
