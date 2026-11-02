"""Édition humaine M2/M3 : la version sauvegardée reste celle du review HITL."""

import asyncio

import pytest
from fastapi import HTTPException

from app.api.v1.endpoints import formation_ia
from app.services.hitl import hitl_helper


@pytest.fixture(autouse=True)
def store_isole(monkeypatch, tmp_path):
    monkeypatch.setattr(hitl_helper, "STORAGE_PATH", tmp_path / "reviews.json")


def modifier(review_id, content, version):
    return asyncio.run(formation_ia.modifier_document_en_attente(
        review_id,
        formation_ia.ManualDocumentEditRequest(content=content, expected_updated_at=version),
        _current_user=object(),
    ))


def test_offre_modifiee_avant_approbation_et_version_protegee():
    review_id = hitl_helper.create_review(
        "agent_m3_technique",
        {"reference": "OT-1", "titre_offre": "Ancien titre", "metadata": {"source": "llm"}},
        "Offre technique",
    )
    version = hitl_helper.get_review(review_id)["updated_at"]

    response = modifier(review_id, {"reference": "OT-1", "titre_offre": "Titre corrigé"}, version)
    saved = hitl_helper.get_review(review_id)

    assert response["success"] is True
    assert saved["data"]["titre_offre"] == "Titre corrigé"
    assert saved["data"]["metadata"] == {"source": "llm"}
    assert saved["status"] == "pending_review"
    assert saved["manual_edits_count"] == 1
    assert len(saved["revision_history"]) == 1
    assert saved["revision_history"][0]["data"]["titre_offre"] == "Ancien titre"
    with pytest.raises(HTTPException) as stale:
        modifier(review_id, {"reference": "OT-1", "titre_offre": "Version obsolète"}, version)
    assert stale.value.status_code == 409

    hitl_helper.approve_review(review_id, "Validé")
    history = hitl_helper.list_reviews(status="approved", agent_id="agent_m3_technique")
    assert any(item["review_id"] == review_id and item["reviewer_note"] == "Validé" for item in history)
    assert hitl_helper.get_review(review_id)["revision_history"][0]["data"]["titre_offre"] == "Ancien titre"
    with pytest.raises(HTTPException) as approved:
        modifier(review_id, {"reference": "OT-1", "titre_offre": "Trop tard"}, saved["updated_at"])
    assert approved.value.status_code == 409


def test_tdr_manuel_regenere_les_exports(monkeypatch):
    class FauxGenerateur:
        def generate(self, tdr_content, client):
            assert tdr_content["titre"] == "TDR corrigé"
            assert client == "ALTIORA PREST"
            return "corrige.docx", "corrige.pdf"

    import app.services.tdr.tdr_document_generator as document_module

    monkeypatch.setattr(document_module, "TDRDocumentGenerator", FauxGenerateur)
    review_id = hitl_helper.create_review(
        "agent_m2_tdr",
        {
            "success": True,
            "data": {"titre": "TDR initial", "objectifs": "Former"},
            "files": {"docx": "initial.docx", "pdf": "initial.pdf"},
            "_inputs": {"brief": {"client": "ALTIORA PREST"}},
        },
        "TDR",
    )
    version = hitl_helper.get_review(review_id)["updated_at"]

    modifier(review_id, {"titre": "TDR corrigé", "objectifs": "Former"}, version)
    saved = hitl_helper.get_review(review_id)["data"]
    assert saved["data"]["titre"] == "TDR corrigé"
    assert saved["files"] == {"docx": "corrige.docx", "pdf": "corrige.pdf"}
    assert saved["_inputs"]["brief"]["client"] == "ALTIORA PREST"
    assert hitl_helper.get_review(review_id)["revision_history"][0]["data"]["data"]["titre"] == "TDR initial"
