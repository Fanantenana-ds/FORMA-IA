import json
from datetime import date
from types import SimpleNamespace
from unittest.mock import MagicMock

from app.api.v1.endpoints.public_registration import _public_formation_details


def _session():
    return SimpleNamespace(
        titre="Formation IA", client="Organisation partenaire", lieu="Antananarivo",
        date_debut=date(2026, 12, 7), date_fin=date(2026, 12, 9),
        opportunite_id="opportunity-id",
    )


def test_trainer_brief_exposes_approved_profile_without_financial_data():
    db = MagicMock()
    db.query.return_value.filter.return_value.order_by.return_value.first.return_value = SimpleNamespace(
        contenu=json.dumps({
            "titre_formation": "Formation IA pratique",
            "formateur_profil": "Formateur expérimenté en IA et pédagogie active.",
            "competences_requises": ["Animation de groupes", "IA générative"],
            "budget_total": 5000000,
            "budget_details": [{"poste": "Animation", "montant": 5000000}],
        })
    )

    details = _public_formation_details(db, _session(), for_trainer=True)

    assert details["formateur_profil"] == "Formateur expérimenté en IA et pédagogie active."
    assert details["competences_requises"] == ["Animation de groupes", "IA générative"]
    assert details["lieu"] == "Antananarivo"
    assert details["date_debut"] == "2026-12-07"
    assert "budget" not in json.dumps(details)
    assert "montant" not in json.dumps(details)


def test_profile_is_not_exposed_on_participant_links_or_without_validated_tdr(monkeypatch):
    db = MagicMock()
    db.query.return_value.filter.return_value.order_by.return_value.first.return_value = SimpleNamespace(
        contenu=json.dumps({"formateur_profil": "Expert IA"})
    )
    assert "formateur_profil" not in _public_formation_details(db, _session())

    db.query.return_value.filter.return_value.order_by.return_value.first.return_value = None
    monkeypatch.setattr("app.services.hitl.list_reviews", lambda **_: [])
    assert _public_formation_details(db, _session(), for_trainer=True)["formateur_profil"] is None


def test_approved_ia_tdr_supplies_trainer_profile_when_backend_document_is_pending(monkeypatch):
    db = MagicMock()
    db.query.return_value.filter.return_value.order_by.return_value.first.return_value = None
    monkeypatch.setattr("app.services.hitl.list_reviews", lambda **_: [
        {"review_id": "older"}, {"review_id": "approved-match"}
    ])
    reviews = {
        "older": {"status": "approved", "data": {
            "_inputs": {"brief": {"opportunite_id": "another-opportunity"}},
            "data": {"formateur_profil": "Mauvais profil"},
        }},
        "approved-match": {"status": "approved", "data": {
            "_inputs": {"brief": {"opportunite_id": "opportunity-id"}},
            "data": {"formateur_profil": "Expert en pédagogie et IA", "budget_total": 9000000},
        }},
    }
    monkeypatch.setattr("app.services.hitl.get_review", reviews.get)

    details = _public_formation_details(db, _session(), for_trainer=True)

    assert details["formateur_profil"] == "Expert en pédagogie et IA"
    assert "budget" not in details
