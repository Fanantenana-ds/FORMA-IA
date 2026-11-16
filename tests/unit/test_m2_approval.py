import asyncio
from unittest.mock import Mock

import pytest
from fastapi import HTTPException

from app.api.v1.routes_tdr import ValidationTDRRequest, approuver_tdr
from app.services import hitl


def test_autre_agent_non_approuve(monkeypatch):
    monkeypatch.setattr(hitl, "get_review", lambda _: {"agent_id": "agent_m3_technique"})
    approve = Mock()
    monkeypatch.setattr(hitl, "approve_review", approve)
    with pytest.raises(HTTPException) as error:
        asyncio.run(approuver_tdr("test-review", ValidationTDRRequest(reviewer_note="Vérifié")))
    assert error.value.status_code == 404
    approve.assert_not_called()


def test_approbation_tdr_utilise_hitl_existant(monkeypatch):
    monkeypatch.setattr(hitl, "get_review", lambda _: {"agent_id": "agent_m2_tdr"})
    approve = Mock(return_value={"status": "approved"})
    monkeypatch.setattr(hitl, "approve_review", approve)
    result = asyncio.run(approuver_tdr("test-review", ValidationTDRRequest(reviewer_note="Source et objectifs vérifiés")))
    assert result["review"]["status"] == "approved"
    approve.assert_called_once_with("test-review", "Source et objectifs vérifiés")
