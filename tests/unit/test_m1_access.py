from unittest.mock import Mock

import pytest
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials

from app.services.veille import access_service as access


def bearer(value):
    return HTTPAuthorizationCredentials(scheme="Bearer", credentials=value)


def test_cle_historique_sans_validation_jwt(monkeypatch):
    monkeypatch.setattr(access.security, "SHARED_INTERNAL_TOKEN", "internal-test")
    validate = Mock(side_effect=AssertionError("DB inutile pour clé interne"))
    monkeypatch.setattr(access, "get_current_user", validate)
    assert access.verify_api_key(bearer("internal-test"), Mock()) is None
    assert access.verify_api_key_sse("internal-test", None, Mock()) is None
    validate.assert_not_called()


def test_jwt_delegue_au_validateur_backend(monkeypatch):
    user = object()
    validate = Mock(return_value=user)
    monkeypatch.setattr(access, "get_current_user", validate)
    credential, db = bearer("session-test"), Mock()
    assert access.verify_api_key_sse(None, credential, db) is user
    validate.assert_called_once_with(credential=credential, db=db)


@pytest.mark.parametrize("code", [401, 403])
def test_session_expiree_revoquee_ou_inactive_refusee(monkeypatch, code):
    monkeypatch.setattr(access, "get_current_user", Mock(side_effect=HTTPException(code, "refus")))
    with pytest.raises(HTTPException) as error:
        access.verify_api_key(bearer("invalid-test"), Mock())
    assert error.value.status_code == code
