# tests/unit/test_rag_etape_h.py
# ============================================================
# TESTS — Étape H (routes RAG restantes, statut, santé)
# ============================================================
# Aucun réseau/base réel : registre redirigé vers tmp_path, faux
# fournisseur d'embeddings, faux dépôt pour /rechercher. Même approche
# d'isolation que test_rag_portfolio_syllabus_questions.py (Étape G) :
# recherche_service.py a sa PROPRE référence importée de
# get_embedding_provider, à patcher séparément de rag_orchestrator.py.
# ============================================================

import asyncio

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.v1.endpoints import rag_ia
import app.orchestrator.rag_orchestrator as rag_orch_module
import app.services.rag.recherche_service as recherche_service_module
import app.services.rag.registry_service as registry_service_module
from app.orchestrator.rag_orchestrator import RagOrchestrator


def run(coro):
    return asyncio.run(coro)


class FauxEmbeddingProvider:
    def __init__(self):
        self.modele_requete = "voyage-4-large"
        self.modele_document = "voyage-4-large"

    async def embed_query(self, texte, **kw):
        return [0.1] * 1024

    async def embed_documents(self, textes):
        return [[0.1] * 1024 for _ in textes]

    class config:
        tpm = 10_000
        rpm = 3


class FauxRepository:
    def modeles_presents(self, collection=None):
        return []

    def rechercher_par_similarite(self, vecteur, collection, top_k, **filtres):
        return []


@pytest.fixture(autouse=True)
def isole(monkeypatch, tmp_path):
    monkeypatch.setattr(registry_service_module, "CHEMIN_REGISTRE_DEFAUT", tmp_path / "index_registry.json")
    monkeypatch.setattr(rag_orch_module, "get_embedding_provider", lambda: FauxEmbeddingProvider())
    monkeypatch.setattr(recherche_service_module, "get_embedding_provider", lambda: FauxEmbeddingProvider())
    monkeypatch.setattr(recherche_service_module, "CHEMIN_CACHE_DEFAUT", tmp_path / "query_cache.json")
    monkeypatch.setattr(recherche_service_module, "_repository_defaut", FauxRepository())
    # Le singleton module-level doit être recréé avec le faux provider ci-dessus.
    monkeypatch.setattr(rag_orch_module, "_orchestrateur_instance", None)


# ============================================================
# Garde-fou de montage — comme test_le_router_de_l_application_monte_m7
# ============================================================

def test_le_router_de_l_application_monte_toutes_les_routes_rag():
    from app.api.v1.router import api_router

    chemins = {route.path for route in api_router.routes}
    assert {
        "/ia/rag/chat",
        "/ia/rag/documents/{doc_hash}/fichier",
        "/ia/rag/formations",
        "/ia/rag/portfolio",
        "/ia/rag/portfolio/{review_id}/exporter",
        "/ia/rag/syllabus",
        "/ia/rag/syllabus/{review_id}/exporter",
        "/ia/rag/generer-questions",
        "/ia/rag/indexer-document",
        "/ia/rag/rechercher",
        "/ia/rag/statut/{doc_hash}",
        "/ia/rag/health",
    } <= chemins


# ============================================================
# RagOrchestrator.preparer_indexation — Python pur, pas d'appel Voyage
# ============================================================

@pytest.fixture
def fichier_test(tmp_path):
    chemin = tmp_path / "support.txt"
    chemin.write_text("Contenu de test pour l'indexation en arrière-plan.", encoding="utf-8")
    return chemin


def test_preparer_indexation_nouveau_fichier(fichier_test):
    orch = RagOrchestrator(repository=FauxRepository())
    info = orch.preparer_indexation(str(fichier_test), "IA_FONDAMENTAUX")

    assert info["deja_indexe"] is False
    assert info["fichier"] == "support.txt"
    assert len(info["hash"]) == 64

    from app.services.rag import registry_service as registre
    entree = registre.obtenir_entree(info["hash"])
    assert entree is not None
    assert entree.statut == "en_cours"


def test_preparer_indexation_deja_indexe(fichier_test, monkeypatch):
    from app.services.rag import registry_service as registre

    orch = RagOrchestrator(repository=FauxRepository())
    hash_fichier = registre.calculer_hash_fichier(str(fichier_test))
    registre.initialiser_entree(hash_fichier, "support.txt", None)
    registre.marquer_termine(
        hash_fichier, nb_pages=1, nb_chunks=1, tokens_estimes=10, modele_embed="voyage-4-large",
    )

    info = orch.preparer_indexation(str(fichier_test), None)
    assert info["deja_indexe"] is True


def test_preparer_indexation_fichier_introuvable():
    orch = RagOrchestrator(repository=FauxRepository())
    with pytest.raises(ValueError, match="introuvable"):
        orch.preparer_indexation("/chemin/qui/n_existe/pas.pdf", None)


# ============================================================
# Routes HTTP — app isolée (mêmes principes que test_m7_facturation.py)
# ============================================================

@pytest.fixture
def api():
    app = FastAPI()
    app.include_router(rag_ia.router, prefix="/api/v1")
    return TestClient(app)


def test_route_indexer_document_planifie_en_arriere_plan(api, fichier_test, monkeypatch):
    appels = []

    async def faux_ingerer_fichier(self, chemin_fichier, formation_code, collection, nom_original):
        appels.append((chemin_fichier, formation_code, collection, nom_original))
        return {"statut": "indexe"}

    monkeypatch.setattr(RagOrchestrator, "ingerer_fichier", faux_ingerer_fichier)

    response = api.post("/api/v1/ia/rag/indexer-document", json={
        "chemin_fichier": str(fichier_test), "formation_code": "IA_FONDAMENTAUX",
    })

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["statut"] == "en_cours"
    assert len(data["hash"]) == 64
    # BackgroundTasks de Starlette s'exécute APRÈS la réponse envoyée, mais
    # TestClient (requests) attend la fin complète de la requête -> déjà exécuté ici.
    assert len(appels) == 1
    assert appels[0][1] == "IA_FONDAMENTAUX"


def test_route_indexer_document_fichier_introuvable_404(api):
    # _gerer_erreur() route tout ValueError contenant "introuvable" vers 404
    # (même convention que /documents/{hash}/fichier et /portfolio/{id}/exporter).
    response = api.post("/api/v1/ia/rag/indexer-document", json={
        "chemin_fichier": "/n/existe/pas.pdf",
    })
    assert response.status_code == 404


def test_route_rechercher_delegue_au_service(api):
    response = api.post("/api/v1/ia/rag/rechercher", json={"requete": "intelligence artificielle"})

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["total"] == 0  # FauxRepository ne retourne rien, MODE STRICT : liste vide, pas d'erreur
    assert data["data"] == []


def test_route_statut_hash_invalide_400(api):
    response = api.get("/api/v1/ia/rag/statut/pas-un-hash-valide")
    assert response.status_code == 400


def test_route_statut_introuvable_404(api):
    response = api.get("/api/v1/ia/rag/statut/" + "a" * 64)
    assert response.status_code == 404


def test_route_statut_trouve_200(api, fichier_test):
    from app.services.rag import registry_service as registre
    hash_fichier = registre.calculer_hash_fichier(str(fichier_test))
    registre.initialiser_entree(hash_fichier, "support.txt", "IA_FONDAMENTAUX")

    response = api.get(f"/api/v1/ia/rag/statut/{hash_fichier}")

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["statut"] == "en_attente"
    assert data["formation_code"] == "IA_FONDAMENTAUX"


def test_route_health(api):
    response = api.get("/api/v1/ia/rag/health")
    data = response.json()

    assert data["success"] is True
    assert data["module"] == "C3"
    assert data["services"]["Assistant documentaire (chat RAG)"] is True
    assert data["implemented_count"] == data["total_services"]
