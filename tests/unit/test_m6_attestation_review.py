import asyncio
from pathlib import Path

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
        items.append({
            "numero_unique": number,
            "pdf_path": str(path),
            "approval_status": "pending_review",
            "participant": {"nom": "NAMBININA", "prenom": "Hantamalala"},
            "content": {
                "titre_attestation": "ATTESTATION DE FORMATION",
                "introduction": "Le Directeur atteste que Hantamalala NAMBININA",
                "corps": "a suivi la formation",
                "details": {"formation": "Formation IA", "dates": "04/11/2026", "lieu": "Antanifotsy", "duree": "1 jour", "formateur": "Formatrice", "domaine": "IA", "niveau": "Débutant"},
                "competences": ["Découvrir l’IA", "Structurer un prompt", "Vérifier une réponse"],
                "cloture": "Délivrée pour servir et valoir ce que de droit.",
                "lieu_emission": "Antananarivo",
                "date_emission": "05/11/2026",
            },
        })
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


def test_un_review_sans_fichier_pdf_ne_bloque_pas_une_nouvelle_generation(review_m6):
    _, items = review_m6
    review_avec_pdf = {"data": {"attestations": items}}
    review_vide = {"data": {"attestations": []}}
    review_pdf_absent = {"data": {"attestations": [{"numero_unique": "ALT-VIDE", "pdf_path": ""}]}}

    assert formation_ia._review_has_generated_attestation_pdf(review_avec_pdf) is True
    assert formation_ia._review_has_generated_attestation_pdf(review_vide) is False
    assert formation_ia._review_has_generated_attestation_pdf(review_pdf_absent) is False


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


def test_modifier_attestation_regenere_pdf_et_conserve_validation_en_attente(review_m6, monkeypatch):
    review_id, items = review_m6
    review = hitl_helper.get_review(review_id)

    def build_pdf(self, result, participant, output_path=None):
        output_path.write_bytes(b"%PDF-1.4 revised")
        return str(output_path)

    monkeypatch.setattr(AttestationGeneratorService, "_build_attestation_pdf", build_pdf)
    content = {**items[0]["content"], "cloture": "Version corrigée après vérification."}
    response = asyncio.run(formation_ia.modifier_attestation(
        review_id,
        items[0]["numero_unique"],
        formation_ia.AttestationEditRequest(content=content, expected_updated_at=review["updated_at"]),
        _current_user=None,
    ))

    edited = response["review"]["data"]["attestations"][0]
    assert response["review"]["status"] == "pending_review"
    assert edited["content"]["cloture"] == "Version corrigée après vérification."
    assert Path(edited["pdf_path"]).read_bytes() == b"%PDF-1.4 revised"
    assert response["review"]["manual_edits_count"] == 1


def test_supprimer_attestation_en_attente_et_refuser_la_derniere(review_m6):
    review_id, items = review_m6
    review = hitl_helper.get_review(review_id)
    response = asyncio.run(formation_ia.supprimer_attestation(
        review_id,
        items[0]["numero_unique"],
        formation_ia.AttestationDeleteRequest(expected_updated_at=review["updated_at"]),
        _current_user=None,
    ))
    assert [item["numero_unique"] for item in response["review"]["data"]["attestations"]] == [items[1]["numero_unique"]]
    assert not Path(items[0]["pdf_path"]).exists()

    updated = response["review"]
    with pytest.raises(HTTPException) as error:
        asyncio.run(formation_ia.supprimer_attestation(
            review_id,
            items[1]["numero_unique"],
            formation_ia.AttestationDeleteRequest(expected_updated_at=updated["updated_at"]),
            _current_user=None,
        ))
    assert error.value.status_code == 409
