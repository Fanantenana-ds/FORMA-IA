import asyncio

import pytest
from fastapi import HTTPException

from app.api.v1.endpoints import formation_ia
from app.services.hitl import hitl_helper
from app.services.formations.attestation_generator_service import AttestationGeneratorService


@pytest.fixture
def review_m6(monkeypatch, tmp_path):
    output_dir = tmp_path / "attestations"
    output_dir.mkdir()
    monkeypatch.setattr(AttestationGeneratorService, "OUTPUT_DIR", output_dir)
    monkeypatch.setattr(hitl_helper, "STORAGE_PATH", tmp_path / "reviews.json")
    items = []
    for number in ("ALT-2026-IA-0001", "ALT-2026-IA-0002"):
        path = output_dir / f"attestation_{number}.pdf"
        path.write_bytes(b"%PDF-1.4 test")
        items.append({"numero_unique": number, "pdf_path": str(path), "approval_status": "pending_review"})
    review_id = hitl_helper.create_review(
        agent_id="agent_5_attestations",
        data={"session_id": "session-1", "attestations": items},
        summary="Lot M6 à valider",
        criticity="critical",
    )
    return review_id, items


def test_pdf_non_approuve_est_previsualisable_mais_pas_telechargeable(review_m6):
    review_id, items = review_m6
    preview = asyncio.run(formation_ia.preview_attestation(review_id, items[0]["numero_unique"], _current_user=None))
    assert preview.media_type == "application/pdf"

    with pytest.raises(HTTPException) as error:
        asyncio.run(formation_ia.telecharger_attestation(review_id, items[0]["numero_unique"], _current_user=None))
    assert error.value.status_code == 403


def test_approbation_individuelle_et_zip_apres_approbation_complete(review_m6):
    review_id, items = review_m6
    request = formation_ia.ApproveReviewRequest(reviewer_note="Vérifiée")

    first = asyncio.run(formation_ia.approuver_attestation(
        review_id, items[0]["numero_unique"], request, _current_user=None,
    ))
    assert first["lot_approved"] is False
    individual = asyncio.run(formation_ia.telecharger_attestation(
        review_id, items[0]["numero_unique"], _current_user=None,
    ))
    assert individual.media_type == "application/pdf"
    with pytest.raises(HTTPException) as error:
        asyncio.run(formation_ia.telecharger_lot_attestations(review_id, _current_user=None))
    assert error.value.status_code == 403

    second = asyncio.run(formation_ia.approuver_attestation(
        review_id, items[1]["numero_unique"], request, _current_user=None,
    ))
    assert second["lot_approved"] is True
    archive = asyncio.run(formation_ia.telecharger_lot_attestations(review_id, _current_user=None))
    assert archive.media_type == "application/zip"
