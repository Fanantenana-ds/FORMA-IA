from datetime import date
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.api.v1.endpoints import formation_ia
from app.models.formation import Inscription, Participant, Presence, Seance, Session as TrainingSession, StatutPresence


class FakeQuery:
    def __init__(self, values):
        self.values = values

    def filter(self, *args):
        return self

    def order_by(self, *args):
        return self

    def first(self):
        return self.values[0] if self.values else None

    def all(self):
        return self.values


class FakeDb:
    def __init__(self, values_by_model):
        self.values_by_model = values_by_model

    def query(self, model):
        return FakeQuery(self.values_by_model.get(model, []))


@pytest.fixture
def m6_data():
    owner_id = uuid4()
    session_id = uuid4()
    participant_id = uuid4()
    seances = [
        SimpleNamespace(id=uuid4(), session_id=session_id, date=date(2026, 10, day), heure_debut="09:00", heure_fin="12:00", theme=f"Module {day}", owner_id=owner_id)
        for day in range(1, 5)
    ]
    participant = SimpleNamespace(id=participant_id, nom="Ranaivo", prenom="Lova", email=None, entreprise=None, owner_id=owner_id)
    session = SimpleNamespace(
        id=session_id, owner_id=owner_id, titre="Formation IA", formation_code="IA_FONDAMENTAUX",
        date_debut=date(2026, 10, 1), date_fin=date(2026, 10, 4), lieu="Antananarivo", formateur_id=None,
    )
    inscription = SimpleNamespace(session_id=session_id, participant_id=participant_id, owner_id=owner_id)
    presences = [
        SimpleNamespace(
            seance_id=seances[index].id, participant_id=participant_id,
            statut=StatutPresence.PRESENT, owner_id=owner_id,
        )
        for index in range(3)
    ]
    db = FakeDb({
        TrainingSession: [session], Seance: seances, Inscription: [inscription],
        Participant: [participant], Presence: presences,
    })
    user = SimpleNamespace(id=owner_id, owner_id=None)
    return session_id, user, db, presences, seances, participant_id


def test_eligibilite_calculee_sur_presences_backend_et_seuil_75(m6_data):
    session_id, user, db, *_ = m6_data
    session, rows, eligible, missing = formation_ia._attestation_session_data(str(session_id), user, db)

    assert session["formation_code"] == "IA_FONDAMENTAUX"
    assert rows[0]["taux_presence"] == 75.0
    assert rows[0]["eligible_attestation"] is False
    assert eligible == []
    assert missing == 1


def test_generation_est_bloquee_si_un_pointage_manque(m6_data):
    session_id, user, db, presences, seances, participant_id = m6_data
    presences.append(SimpleNamespace(
        seance_id=seances[3].id, participant_id=participant_id,
        statut=StatutPresence.ABSENT, owner_id=user.id,
    ))

    _, rows, eligible, missing = formation_ia._attestation_session_data(str(session_id), user, db)

    assert missing == 0
    assert rows[0]["taux_presence"] == 75.0
    assert eligible == rows


def test_generation_rejette_un_identifiant_de_session_invalide():
    user = SimpleNamespace(id=uuid4(), owner_id=None)
    with pytest.raises(Exception, match="Identifiant de session invalide"):
        formation_ia._attestation_session_data("session-invalide", user, FakeDb({}))
