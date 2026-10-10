# tests/test_backend_bloc_j.py
# Tests des routes Backend Bloc J — Supports RAG
# (POST /documents/upload, GET /documents/supports, DELETE /documents/supports/{hash})
#
# Isolation :
#   - db_isolee (conftest) : transaction annulée — aucune ligne en base
#   - tmp_path pytest : dossier temporaire pour les fichiers RAG uploadés
#   - monkeypatch sur DOSSIER_FICHIERS_RAG et CHEMIN_REGISTRE_DEFAUT
#   - mock KnowledgeRepository.supprimer_par_hash (pas d'appel pgvector réel)

import hashlib
import io
import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


# =============================================================================
# FIXTURE — isolation disque + registre
# =============================================================================

@pytest.fixture
def rag_env(db_isolee, tmp_path, monkeypatch):
    """
    Redirige DOSSIER_FICHIERS_RAG et LocalStorageService vers tmp_path/fichiers
    et CHEMIN_REGISTRE_DEFAUT vers tmp_path/registry.json.
    Retourne (client, dossier_fichiers, chemin_registry).
    """
    from fastapi.testclient import TestClient
    from app.main import app
    from app.core.dependencies import get_current_user
    from tests.conftest import FakeUser

    dossier = tmp_path / "fichiers"
    dossier.mkdir()
    registry_path = tmp_path / "registry.json"

    # Patch du dossier fichiers dans le module endpoint (liste + suppression)
    import app.api.v1.endpoints.document as doc_module
    monkeypatch.setattr(doc_module, "DOSSIER_FICHIERS_RAG", dossier)

    # Patch du storage service : get_storage() retourne une instance pointant vers tmp_path
    from app.services.storage.storage_service import LocalStorageService
    storage_test = LocalStorageService.__new__(LocalStorageService)
    storage_test._dossier = dossier

    import app.services.storage as storage_module
    monkeypatch.setattr(storage_module, "get_storage", lambda: storage_test)

    import app.api.v1.endpoints.document as doc_ep
    monkeypatch.setattr(doc_ep, "get_storage", lambda: storage_test)

    # Patch du chemin registry dans registry_service
    import app.services.rag.registry_service as reg_module
    monkeypatch.setattr(reg_module, "CHEMIN_REGISTRE_DEFAUT", registry_path)

    # Authentification DIRECTION
    app.dependency_overrides[get_current_user] = lambda: FakeUser(role="DIRECTION")
    client = TestClient(app)

    yield client, dossier, registry_path

    app.dependency_overrides.pop(get_current_user, None)


def _hash_contenu(contenu: bytes) -> str:
    return hashlib.sha256(contenu).hexdigest()


def _contenu_pdf_factice() -> bytes:
    """Contenu minimal reconnu comme non-vide."""
    return b"%PDF-1.4 factice test\n" + b"A" * 100


# =============================================================================
# UPLOAD — POST /documents/upload
# =============================================================================

class TestUploadSupport:
    def test_upload_pdf_ok(self, rag_env):
        client, dossier, registry_path = rag_env
        contenu = _contenu_pdf_factice()
        r = client.post(
            "/api/v1/documents/upload",
            data={"formation_code": "IA-2026", "collection": "support"},
            files={"fichier": ("cours.pdf", io.BytesIO(contenu), "application/pdf")},
        )
        assert r.status_code == 201
        body = r.json()
        assert body["success"] is True
        assert body["fichier"] == "cours.pdf"
        assert body["formation_code"] == "IA-2026"
        assert body["statut"] == "en_attente"
        assert body["deja_present"] is False
        # Fichier physique créé
        hash_attendu = _hash_contenu(contenu)
        assert (dossier / f"{hash_attendu}.pdf").exists()
        # Registre mis à jour
        assert registry_path.exists()
        data_reg = json.loads(registry_path.read_text())
        assert hash_attendu in data_reg

    def test_upload_idempotent(self, rag_env):
        """Uploader deux fois le même contenu retourne deja_present=True au 2e appel."""
        client, dossier, registry_path = rag_env
        contenu = _contenu_pdf_factice()
        fichier_io = lambda: ("cours.pdf", io.BytesIO(contenu), "application/pdf")

        r1 = client.post("/api/v1/documents/upload",
                         data={"formation_code": "IA-2026"},
                         files={"fichier": fichier_io()})
        assert r1.status_code == 201
        assert r1.json()["deja_present"] is False

        r2 = client.post("/api/v1/documents/upload",
                         data={"formation_code": "IA-2026"},
                         files={"fichier": fichier_io()})
        assert r2.status_code == 201
        assert r2.json()["deja_present"] is True

    def test_upload_extension_invalide(self, rag_env):
        client, _, _ = rag_env
        r = client.post(
            "/api/v1/documents/upload",
            data={},
            files={"fichier": ("script.exe", io.BytesIO(b"MZ"), "application/octet-stream")},
        )
        assert r.status_code == 422
        assert "exe" in r.json()["detail"].lower()

    def test_upload_fichier_vide(self, rag_env):
        client, _, _ = rag_env
        r = client.post(
            "/api/v1/documents/upload",
            data={},
            files={"fichier": ("vide.pdf", io.BytesIO(b""), "application/pdf")},
        )
        assert r.status_code == 422

    def test_upload_sans_auth_refuse(self, db_isolee, tmp_path, monkeypatch):
        """Sans authentification, la route doit retourner 401 ou 403."""
        from fastapi.testclient import TestClient
        from app.main import app
        import app.api.v1.endpoints.document as doc_module
        monkeypatch.setattr(doc_module, "DOSSIER_FICHIERS_RAG", tmp_path / "f")
        client = TestClient(app, raise_server_exceptions=False)
        r = client.post(
            "/api/v1/documents/upload",
            data={},
            files={"fichier": ("cours.pdf", io.BytesIO(b"test"), "application/pdf")},
        )
        assert r.status_code in (401, 403)

    def test_upload_docx_ok(self, rag_env):
        client, dossier, _ = rag_env
        contenu = b"PK" + b"\x00" * 50  # header ZIP (DOCX)
        r = client.post(
            "/api/v1/documents/upload",
            data={"formation_code": "RH-2026"},
            files={"fichier": ("support.docx", io.BytesIO(contenu), "application/vnd.openxmlformats")},
        )
        assert r.status_code == 201
        assert (dossier / f"{_hash_contenu(contenu)}.docx").exists()


# =============================================================================
# LISTE — GET /documents/supports
# =============================================================================

class TestListerSupports:
    def test_liste_vide(self, rag_env):
        client, _, _ = rag_env
        r = client.get("/api/v1/documents/rag/supports")
        assert r.status_code == 200
        assert r.json()["total"] == 0
        assert r.json()["data"] == []

    def test_liste_apres_upload(self, rag_env):
        client, _, _ = rag_env
        contenu = _contenu_pdf_factice()
        client.post("/api/v1/documents/upload",
                    data={"formation_code": "IA-2026"},
                    files={"fichier": ("cours.pdf", io.BytesIO(contenu), "application/pdf")})

        r = client.get("/api/v1/documents/rag/supports")
        assert r.status_code == 200
        body = r.json()
        assert body["total"] == 1
        doc = body["data"][0]
        assert doc["fichier"] == "cours.pdf"
        assert doc["statut"] == "en_attente"
        assert doc["fichier_disponible"] is True

    def test_filtre_formation_code(self, rag_env):
        client, _, _ = rag_env
        # Upload 2 fichiers avec des codes différents
        for i, code in enumerate(["IA-2026", "RH-2026"]):
            contenu = _contenu_pdf_factice() + bytes([i])  # hash différent
            client.post("/api/v1/documents/upload",
                        data={"formation_code": code},
                        files={"fichier": (f"cours{i}.pdf", io.BytesIO(contenu), "application/pdf")})

        r = client.get("/api/v1/documents/rag/supports?formation_code=IA-2026")
        assert r.status_code == 200
        assert r.json()["total"] == 1
        assert r.json()["data"][0]["formation_code"] == "IA-2026"

    def test_filtre_statut(self, rag_env):
        client, _, _ = rag_env
        contenu = _contenu_pdf_factice()
        client.post("/api/v1/documents/upload",
                    data={"formation_code": "IA-2026"},
                    files={"fichier": ("cours.pdf", io.BytesIO(contenu), "application/pdf")})

        r_ok = client.get("/api/v1/documents/rag/supports?statut=en_attente")
        assert r_ok.json()["total"] == 1

        r_vide = client.get("/api/v1/documents/rag/supports?statut=indexe")
        assert r_vide.json()["total"] == 0


# =============================================================================
# SUPPRESSION — DELETE /documents/supports/{hash}
# =============================================================================

class TestSupprimerSupport:
    def _upload(self, client, contenu=None, code="IA-2026"):
        contenu = contenu or _contenu_pdf_factice()
        r = client.post("/api/v1/documents/upload",
                        data={"formation_code": code},
                        files={"fichier": ("cours.pdf", io.BytesIO(contenu), "application/pdf")})
        assert r.status_code == 201
        return r.json()["hash"], contenu

    def test_suppression_ok(self, rag_env):
        client, dossier, registry_path = rag_env
        with patch("app.services.rag.knowledge_repository.KnowledgeRepository") as mock_repo_cls:
            mock_repo = MagicMock()
            mock_repo.supprimer_par_hash.return_value = 5
            mock_repo_cls.return_value = mock_repo

            doc_hash, contenu = self._upload(client)
            chemin_fichier = dossier / f"{doc_hash}.pdf"
            assert chemin_fichier.exists()

            r = client.delete(f"/api/v1/documents/rag/supports/{doc_hash}")
            assert r.status_code == 200
            body = r.json()
            assert body["success"] is True
            assert body["hash"] == doc_hash
            assert body["nb_chunks_supprimes"] == 5
            assert body["fichier_supprime"] is True

            # Fichier physique supprimé
            assert not chemin_fichier.exists()
            # Registre nettoyé
            data_reg = json.loads(registry_path.read_text())
            assert doc_hash not in data_reg

    def test_suppression_hash_inexistant(self, rag_env):
        client, _, _ = rag_env
        hash_fictif = "a" * 64
        r = client.delete(f"/api/v1/documents/rag/supports/{hash_fictif}")
        assert r.status_code == 404

    def test_suppression_hash_invalide(self, rag_env):
        client, _, _ = rag_env
        r = client.delete("/api/v1/documents/rag/supports/hash-invalide-trop-court")
        assert r.status_code == 422

    def test_suppression_comptable_refuse(self, db_isolee, tmp_path, monkeypatch):
        """Le rôle COMPTABLE ne peut pas supprimer un support RAG."""
        from fastapi.testclient import TestClient
        from app.main import app
        from app.core.dependencies import get_current_user
        from tests.conftest import FakeUser
        import app.api.v1.endpoints.document as doc_module
        import app.services.rag.registry_service as reg_module

        dossier = tmp_path / "f2"
        dossier.mkdir()
        reg_path = tmp_path / "r2.json"
        monkeypatch.setattr(doc_module, "DOSSIER_FICHIERS_RAG", dossier)
        monkeypatch.setattr(reg_module, "CHEMIN_REGISTRE_DEFAUT", reg_path)

        app.dependency_overrides[get_current_user] = lambda: FakeUser(role="DIRECTION")
        client_dir = TestClient(app)

        # Upload
        contenu = _contenu_pdf_factice()
        r = client_dir.post("/api/v1/documents/upload",
                            data={},
                            files={"fichier": ("cours.pdf", io.BytesIO(contenu), "application/pdf")})
        doc_hash = r.json()["hash"]
        app.dependency_overrides.pop(get_current_user, None)

        # Essai suppression avec rôle COMPTABLE
        app.dependency_overrides[get_current_user] = lambda: FakeUser(role="COMPTABLE")
        client_cpt = TestClient(app)
        r2 = client_cpt.delete(f"/api/v1/documents/rag/supports/{doc_hash}")
        assert r2.status_code == 403
        app.dependency_overrides.pop(get_current_user, None)
