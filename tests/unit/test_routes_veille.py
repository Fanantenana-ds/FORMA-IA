# ============================================================
# TESTS — app/api/v1/routes_veille.py (M1)
# ============================================================
# Aucun appel Tavily/Groq/Backend réel : l'orchestrateur module-level
# (routes_veille.orchestrator) et les services associés sont doublés.
# ============================================================

import io

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.v1 import routes_veille
from app.services.veille.auto_detection_service import DetectionAutoEnCours


@pytest.fixture
def client():
    app = FastAPI()
    app.include_router(routes_veille.router)
    return TestClient(app)


def _async(fn):
    async def wrapper(*args, **kwargs):
        return fn(*args, **kwargs)
    return wrapper


RESULTAT_VIDE = {
    "opportunities": [], "market_signals": [], "total": 0, "status": "success",
    "ai_provider": "groq", "statistics": {}, "notes": "x",
}


def _resultat_avec_opportunites():
    return {
        "opportunities": [
            {"title": "Haute", "score": 90, "confidence": 0.9},
            {"title": "Basse", "score": 5, "confidence": 0.2},
        ],
        "market_signals": [], "total": 2, "status": "success",
        "ai_provider": "groq", "statistics": {}, "notes": "x",
    }


# ---- POST /ia/veille/rechercher ----

def test_rechercher_success(client, monkeypatch):
    monkeypatch.setattr(routes_veille.orchestrator, "analyser_opportunites", _async(lambda query: _resultat_avec_opportunites()))
    resp = client.post("/ia/veille/rechercher", json={"query": "formation IA", "min_score": 0, "limit": 20})
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert body["data"]["total"] == 2


def test_rechercher_filtre_min_score(client, monkeypatch):
    monkeypatch.setattr(routes_veille.orchestrator, "analyser_opportunites", _async(lambda query: _resultat_avec_opportunites()))
    resp = client.post("/ia/veille/rechercher", json={"query": "formation IA", "min_score": 50, "limit": 20})
    body = resp.json()
    assert body["data"]["total"] == 1
    assert body["data"]["opportunities"][0]["title"] == "Haute"


def test_rechercher_query_trop_courte(client):
    resp = client.post("/ia/veille/rechercher", json={"query": "a"})
    assert resp.status_code == 422


def test_rechercher_exception_renvoie_500(client, monkeypatch):
    async def echoue(query):
        raise RuntimeError("Tavily indisponible")

    monkeypatch.setattr(routes_veille.orchestrator, "analyser_opportunites", echoue)
    resp = client.post("/ia/veille/rechercher", json={"query": "formation IA"})
    assert resp.status_code == 500


# ---- POST /ia/veille/detecter ----

def test_detecter_success_sans_corps(client, monkeypatch):
    monkeypatch.setattr(routes_veille.auto_detection, "executer_detection", _async(
        lambda orch, declenchement, min_score, limit, sync_backend: {"mode": "automatique", "total": 0}
    ))
    resp = client.post("/ia/veille/detecter")
    assert resp.status_code == 200
    assert resp.json()["success"] is True


def test_detecter_deja_en_cours(client, monkeypatch):
    async def echoue(orch, declenchement, min_score, limit, sync_backend):
        raise DetectionAutoEnCours("Déjà en cours")

    monkeypatch.setattr(routes_veille.auto_detection, "executer_detection", echoue)
    resp = client.post("/ia/veille/detecter")
    assert resp.status_code == 409


def test_detecter_exception_renvoie_500(client, monkeypatch):
    async def echoue(orch, declenchement, min_score, limit, sync_backend):
        raise RuntimeError("Erreur inattendue")

    monkeypatch.setattr(routes_veille.auto_detection, "executer_detection", echoue)
    resp = client.post("/ia/veille/detecter")
    assert resp.status_code == 500


def test_detecter_statut(client, monkeypatch):
    monkeypatch.setattr(routes_veille.auto_detection, "est_en_cours", lambda: False)
    monkeypatch.setattr(routes_veille.auto_detection, "get_config", lambda: {"enabled": False})
    monkeypatch.setattr(routes_veille.auto_detection, "lire_etat", lambda: None)
    resp = client.get("/ia/veille/detecter/statut")
    assert resp.status_code == 200
    assert resp.json()["data"]["en_cours"] is False


# ---- POST /ia/veille/analyser-texte ----

def test_analyser_texte_success(client, monkeypatch):
    monkeypatch.setattr(routes_veille.orchestrator, "analyser_texte", _async(lambda texte, source: RESULTAT_VIDE))
    resp = client.post("/ia/veille/analyser-texte", json={"texte": "Un appel d'offre pour une formation."})
    assert resp.status_code == 200
    assert resp.json()["success"] is True


def test_analyser_texte_vide_apres_strip(client):
    resp = client.post("/ia/veille/analyser-texte", json={"texte": "  "})
    assert resp.status_code == 400


def test_analyser_texte_exception_renvoie_500(client, monkeypatch):
    async def echoue(texte, source):
        raise RuntimeError("Groq indisponible")

    monkeypatch.setattr(routes_veille.orchestrator, "analyser_texte", echoue)
    resp = client.post("/ia/veille/analyser-texte", json={"texte": "Un texte valide."})
    assert resp.status_code == 500


# ---- POST /ia/veille/analyser-pdf ----

def test_analyser_pdf_extension_invalide(client):
    resp = client.post(
        "/ia/veille/analyser-pdf",
        files={"file": ("document.txt", b"contenu", "text/plain")},
    )
    assert resp.status_code == 400


def test_analyser_pdf_vide(client):
    resp = client.post(
        "/ia/veille/analyser-pdf",
        files={"file": ("vide.pdf", b"", "application/pdf")},
    )
    assert resp.status_code == 400


def test_analyser_pdf_trop_volumineux(client):
    contenu = b"x" * (15 * 1024 * 1024 + 1)
    resp = client.post(
        "/ia/veille/analyser-pdf",
        files={"file": ("gros.pdf", contenu, "application/pdf")},
    )
    assert resp.status_code == 413


def test_analyser_pdf_invalide_ou_corrompu(client):
    resp = client.post(
        "/ia/veille/analyser-pdf",
        files={"file": ("corrompu.pdf", b"ceci n'est pas un PDF valide", "application/pdf")},
    )
    assert resp.status_code == 400


def test_analyser_pdf_aucun_texte_exploitable(client, monkeypatch):
    class FausseePage:
        def extract_text(self):
            return ""

    class FauxReader:
        def __init__(self, *a, **k):
            self.pages = [FausseePage()]

    monkeypatch.setattr(routes_veille.PyPDF2, "PdfReader", FauxReader)
    resp = client.post(
        "/ia/veille/analyser-pdf",
        files={"file": ("scan_image.pdf", b"%PDF-1.4 ...", "application/pdf")},
    )
    assert resp.status_code == 400
    assert "Aucun texte" in resp.json()["detail"]


def test_analyser_pdf_success(client, monkeypatch):
    class FausseePage:
        def extract_text(self):
            return "Appel d'offre pour une formation en IA."

    class FauxReader:
        def __init__(self, *a, **k):
            self.pages = [FausseePage()]

    monkeypatch.setattr(routes_veille.PyPDF2, "PdfReader", FauxReader)
    monkeypatch.setattr(routes_veille.orchestrator, "analyser_texte", _async(lambda texte, source: RESULTAT_VIDE))

    resp = client.post(
        "/ia/veille/analyser-pdf",
        files={"file": ("ao.pdf", b"%PDF-1.4 ...", "application/pdf")},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert body["file"]["filename"] == "ao.pdf"


def test_analyser_pdf_exception_apres_extraction_renvoie_500(client, monkeypatch):
    class FausseePage:
        def extract_text(self):
            return "Texte valide."

    class FauxReader:
        def __init__(self, *a, **k):
            self.pages = [FausseePage()]

    monkeypatch.setattr(routes_veille.PyPDF2, "PdfReader", FauxReader)

    async def echoue(texte, source):
        raise RuntimeError("Groq indisponible")

    monkeypatch.setattr(routes_veille.orchestrator, "analyser_texte", echoue)

    resp = client.post(
        "/ia/veille/analyser-pdf",
        files={"file": ("ao.pdf", b"%PDF-1.4 ...", "application/pdf")},
    )
    assert resp.status_code == 500


# ---- POST /benchmark ----

def test_benchmark_success(client, monkeypatch):
    monkeypatch.setattr(routes_veille.BenchmarkRunner, "run", _async(lambda self, limit: {"precision": 0.9}))
    resp = client.post("/benchmark?limit=5")
    assert resp.status_code == 200
    assert resp.json()["status"] == "success"
