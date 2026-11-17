from unittest.mock import MagicMock

from sqlalchemy.exc import IntegrityError

from app.schemas.facture import FactureCreate
from app.services.facture_service import FactureService


def test_generer_numero_uses_global_sequence_when_tenant_has_no_visible_factures():
    db = MagicMock()
    db.execute.return_value.scalars.return_value.all.return_value = [
        "FACT-2026-0001",
        "FACT-2026-0004",
    ]

    numero = FactureService(db)._generer_numero()

    assert numero == "FACT-2026-0005"
    db.query.assert_not_called()


def test_emettre_facture_recalcule_numero_apres_collision_concurrente():
    db = MagicMock()
    db.info = {"tenant_owner_id": "00000000-0000-0000-0000-000000000001"}
    db.execute.return_value.scalars.return_value.all.side_effect = [
        ["FACT-2026-0004"],
        ["FACT-2026-0005"],
    ]
    db.commit.side_effect = [
        IntegrityError(
            "INSERT facture",
            {},
            Exception("UNIQUE constraint failed: factures.numero"),
        ),
        None,
    ]

    facture = FactureService(db).emettre_facture(
        FactureCreate(client="Client test", montant=1000, tva_taux=20)
    )

    assert facture.numero == "FACT-2026-0006"
    assert facture.owner_id == db.info["tenant_owner_id"]
    assert db.rollback.call_count == 1
    assert db.commit.call_count == 2

