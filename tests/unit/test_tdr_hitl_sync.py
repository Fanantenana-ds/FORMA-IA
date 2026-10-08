# tests/unit/test_tdr_hitl_sync.py
# ============================================================
# Correction 1b — Mission "Étape 1"
# ============================================================
# Le TDR (M2) doit passer par un review HITL AVANT toute synchronisation
# Backend (même mécanisme que M3/offre_orchestrator.py) : AVANT cette
# correction, TdrOrchestrator.generate() envoyait le TDR au Backend
# directement (sync_tdr_to_backend), sans aucune validation humaine —
# non-conformité au CDC (§12 : "HITL généralisé à tous les modules
# produisant un contenu à diffusion externe").
#
# Rien de réel : store HITL et registre de sync redirigés vers un dossier
# temporaire, Backend simulé (base_sync.backend_request remplacé), LLM
# désactivé (TDRService/document_generator doublés directement).
# ============================================================

import asyncio
import uuid

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.v1 import routes_tdr
from app.orchestrator.tdr_orchestrator import TdrOrchestrator
from app.services.backend_sync import base_sync, review_sync
from app.services.hitl import hitl_helper

BRIEF = {
    "client": "Ministère de la Santé",
    "objectifs": "Former 50 agents à l'IA médicale",
    "public": "Agents de santé",
    "duree": "5 jours",
}


def run(coro):
    return asyncio.run(coro)


def new_id() -> str:
    return str(uuid.uuid4())


@pytest.fixture(autouse=True)
def isole(monkeypatch, tmp_path):
    monkeypatch.setattr(hitl_helper, "STORAGE_PATH", tmp_path / "hitl_reviews.json")
    monkeypatch.setattr(review_sync, "REGISTRY_PATH", tmp_path / "registry.json")
    monkeypatch.setenv("BACKEND_SYNC_ENABLED", "true")
    monkeypatch.setenv("BACKEND_API_URL", "http://backend.test/api/v1")
    base_sync.reset_token_cache()
    yield
    base_sync.reset_token_cache()


class FakeBackend:
    def __init__(self):
        self.calls = []

    async def __call__(self, method, path, *, json=None, params=None,
                       timeout=None, transport=None):
        self.calls.append((method, path, json))
        if method == "POST":
            return {"ok": True, "status_code": 201, "data": {"id": new_id()},
                    "error": None, "absent": False}
        return {"ok": True, "status_code": 200, "data": {}, "error": None,
                "absent": False}

    def posts(self):
        return [c for c in self.calls if c[0] == "POST"]


@pytest.fixture
def backend(monkeypatch):
    fake = FakeBackend()
    monkeypatch.setattr(base_sync, "backend_request", fake)
    return fake


def tdr_genere(orch, monkeypatch, brief=None):
    async def faux_tdr_service_generate(b):
        return {"titre": "TDR Formation IA médicale", "client": brief.get("client") if brief else BRIEF["client"]}

    def faux_document_generator_generate(tdr_content, client):
        return ("tdr_test.docx", "tdr_test.pdf")

    monkeypatch.setattr(orch.tdr_service, "generate", faux_tdr_service_generate)
    monkeypatch.setattr(orch.document_generator, "generate", faux_document_generator_generate)
    return run(orch.generate(dict(brief or BRIEF)))


# ============================================================
# generate() ne synchronise plus directement
# ============================================================

def test_generate_ne_synchronise_pas_directement(monkeypatch, backend):
    orch = TdrOrchestrator()
    r1 = tdr_genere(orch, monkeypatch)

    assert r1["_review_status"] == "pending_review"
    assert backend.calls == []  # AUCUN appel Backend avant approbation


# ============================================================
# synchroniser_backend() — garde-fous HITL
# ============================================================

def test_sync_refuse_un_review_non_approuve(monkeypatch, backend):
    orch = TdrOrchestrator()
    r1 = tdr_genere(orch, monkeypatch)

    with pytest.raises(ValueError, match="non approuvé"):
        run(orch.synchroniser_backend(r1["_review_id"], opportunite_id=new_id()))
    assert backend.calls == []


def test_sync_refuse_un_review_rejete(monkeypatch, backend):
    orch = TdrOrchestrator()
    r1 = tdr_genere(orch, monkeypatch)
    hitl_helper.reject_review(r1["_review_id"], "objectifs imprécis")

    with pytest.raises(ValueError, match="non approuvé"):
        run(orch.synchroniser_backend(r1["_review_id"], opportunite_id=new_id()))


def test_sync_refuse_un_review_d_un_autre_agent(monkeypatch, backend):
    from app.services.hitl import create_review
    autre_review = create_review(
        agent_id="agent_m3_complete", data={}, summary="autre agent", criticity="critical",
    )
    hitl_helper.approve_review(autre_review)

    orch = TdrOrchestrator()
    with pytest.raises(ValueError, match="agent_m2_tdr"):
        run(orch.synchroniser_backend(autre_review, opportunite_id=new_id()))


def test_sync_approuve_envoie_et_une_seule_fois(monkeypatch, backend):
    orch = TdrOrchestrator()
    r1 = tdr_genere(orch, monkeypatch)
    hitl_helper.approve_review(r1["_review_id"])
    opp_id = new_id()

    premier = run(orch.synchroniser_backend(r1["_review_id"], opportunite_id=opp_id))

    assert premier["already_synced"] is False
    assert premier["backend_sync"]["sent"] and premier["backend_sync"]["verified"]
    post = backend.posts()[0]
    assert post[1] == "/documents/tdr"
    assert post[2]["opportunite_id"] == opp_id

    # 2e appel : aucun nouvel envoi
    deuxieme = run(orch.synchroniser_backend(r1["_review_id"], opportunite_id=opp_id))
    assert deuxieme["already_synced"] is True
    assert len(backend.posts()) == 1

    # force=True : nouvel envoi volontaire
    run(orch.synchroniser_backend(r1["_review_id"], opportunite_id=opp_id, force=True))
    assert len(backend.posts()) == 2


def test_sync_lit_opportunite_id_dans_le_brief_memorise(monkeypatch, backend):
    opp_id = new_id()
    orch = TdrOrchestrator()
    r1 = tdr_genere(orch, monkeypatch, brief={**BRIEF, "opportunite_id": opp_id})
    hitl_helper.approve_review(r1["_review_id"])

    run(orch.synchroniser_backend(r1["_review_id"]))
    assert backend.posts()[0][2]["opportunite_id"] == opp_id


def test_sync_desactivee_n_envoie_rien(monkeypatch, backend):
    monkeypatch.setenv("BACKEND_SYNC_ENABLED", "false")
    orch = TdrOrchestrator()
    r1 = tdr_genere(orch, monkeypatch)
    hitl_helper.approve_review(r1["_review_id"])

    result = run(orch.synchroniser_backend(r1["_review_id"], opportunite_id=new_id()))

    assert result["backend_sync"]["enabled"] is False
    assert backend.calls == []
    assert review_sync.get_synced(r1["_review_id"]) is None


# ============================================================
# Route POST /ia/tdr/synchroniser
# ============================================================

@pytest.fixture
def api():
    app = FastAPI()
    app.include_router(routes_tdr.router)
    return TestClient(app)


def test_route_tdr_synchroniser(api, monkeypatch, backend):
    monkeypatch.setattr(routes_tdr, "orchestrator", TdrOrchestrator())
    r1 = tdr_genere(routes_tdr.orchestrator, monkeypatch)

    refuse = api.post("/ia/tdr/synchroniser",
                      json={"review_id": r1["_review_id"], "opportunite_id": new_id()})
    assert refuse.status_code == 422 and "non approuvé" in refuse.json()["detail"]

    hitl_helper.approve_review(r1["_review_id"])
    ok = api.post("/ia/tdr/synchroniser",
                  json={"review_id": r1["_review_id"], "opportunite_id": new_id()})
    body = ok.json()
    assert ok.status_code == 200 and body["success"] is True
    assert body["message"].startswith("Synchronisé avec le Backend")

    encore = api.post("/ia/tdr/synchroniser",
                      json={"review_id": r1["_review_id"], "opportunite_id": new_id()})
    assert "Déjà synchronisé" in encore.json()["message"]
    assert len(backend.posts()) == 1


def test_route_generer_tdr_expose_le_review_id(api, monkeypatch):
    monkeypatch.setattr(routes_tdr, "orchestrator", TdrOrchestrator())

    async def faux_tdr_service_generate(b):
        return {"titre": "TDR Test"}

    def faux_document_generator_generate(tdr_content, client):
        return ("t.docx", "t.pdf")

    monkeypatch.setattr(routes_tdr.orchestrator.tdr_service, "generate", faux_tdr_service_generate)
    monkeypatch.setattr(routes_tdr.orchestrator.document_generator, "generate", faux_document_generator_generate)

    resp = api.post("/ia/tdr/generer", json=BRIEF)
    body = resp.json()
    assert resp.status_code == 200
    assert body["review_status"] == "pending_review"
    assert body["review_id"]
