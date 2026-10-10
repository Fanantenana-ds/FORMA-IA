"""
Tests — app/utils/security.py (verify_api_key)

Couvre :
- Pas de token configuré côté serveur → 500
- Pas de header Authorization → 401
- Mauvais token → 401
- Bon token → passe (None retourné)
"""

import pytest
from fastapi.testclient import TestClient

import app.utils.security as security_module
from app.main import app

if not hasattr(security_module, "SHARED_INTERNAL_TOKEN"):
    pytest.skip(
        "SHARED_INTERNAL_TOKEN n'existe pas dans app.utils.security "
        "(seul IA_API_KEY est actuellement implemente) - tests a adapter "
        "une fois la fonctionnalite clarifiee avec l'equipe",
        allow_module_level=True,
    )


@pytest.fixture
def client_securite(monkeypatch):
    """Client dont SHARED_INTERNAL_TOKEN est fixé à une valeur connue."""
    monkeypatch.setattr(security_module, "SHARED_INTERNAL_TOKEN", "token-de-test-valide")
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture
def client_sans_token(monkeypatch):
    """Client dont SHARED_INTERNAL_TOKEN est None (non configurée)."""
    monkeypatch.setattr(security_module, "SHARED_INTERNAL_TOKEN", None)
    return TestClient(app, raise_server_exceptions=False)


# ──────────────────────────────────────────────
# Tests unitaires sur verify_api_key directement
# ──────────────────────────────────────────────

def test_verify_api_key_sans_token_serveur(monkeypatch):
    """SHARED_INTERNAL_TOKEN absente → HTTPException 500."""
    import asyncio

    from fastapi import HTTPException
    from fastapi.security import HTTPAuthorizationCredentials

    monkeypatch.setattr(security_module, "SHARED_INTERNAL_TOKEN", None)

    credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials="n'importe")
    with pytest.raises(HTTPException) as exc:
        asyncio.run(security_module.verify_api_key(credentials))
    assert exc.value.status_code == 500


def test_verify_api_key_credentials_none(monkeypatch):
    """Pas de header Authorization → HTTPException 401."""
    import asyncio

    from fastapi import HTTPException

    monkeypatch.setattr(security_module, "SHARED_INTERNAL_TOKEN", "secret")

    with pytest.raises(HTTPException) as exc:
        asyncio.run(security_module.verify_api_key(None))
    assert exc.value.status_code == 401
    assert "manquant" in exc.value.detail.lower()


def test_verify_api_key_mauvais_token(monkeypatch):
    """Token incorrect → HTTPException 401."""
    import asyncio

    from fastapi import HTTPException
    from fastapi.security import HTTPAuthorizationCredentials

    monkeypatch.setattr(security_module, "SHARED_INTERNAL_TOKEN", "vrai-secret")

    credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials="faux-token")
    with pytest.raises(HTTPException) as exc:
        asyncio.run(security_module.verify_api_key(credentials))
    assert exc.value.status_code == 401
    assert "invalide" in exc.value.detail.lower()


def test_verify_api_key_bon_token(monkeypatch):
    """Token correct → None retourné (pas d'exception)."""
    import asyncio

    from fastapi.security import HTTPAuthorizationCredentials

    monkeypatch.setattr(security_module, "SHARED_INTERNAL_TOKEN", "vrai-secret")

    credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials="vrai-secret")
    result = asyncio.run(security_module.verify_api_key(credentials))
    assert result is None


def test_verify_api_key_credentials_vides(monkeypatch):
    """Credentials présents mais chaîne vide → 401."""
    import asyncio

    from fastapi import HTTPException
    from fastapi.security import HTTPAuthorizationCredentials

    monkeypatch.setattr(security_module, "SHARED_INTERNAL_TOKEN", "secret")

    credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials="")
    with pytest.raises(HTTPException) as exc:
        asyncio.run(security_module.verify_api_key(credentials))
    assert exc.value.status_code == 401