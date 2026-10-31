import asyncio

from app.api.v1.endpoints.vocal_ia import (
    ExecutionVocaleRequest,
    executer_commande_vocale,
)


def run(coro):
    return asyncio.run(coro)


def test_execution_vocale_exige_confirmation():
    result = run(executer_commande_vocale(
        ExecutionVocaleRequest(action="generer_formulaires"), principal=None
    ))
    assert result.success is False
    assert result.etat == "confirmation_requise"


def test_execution_vocale_refuse_support_absent(monkeypatch):
    from app.services.vocal import prerequisite_service
    monkeypatch.setattr(prerequisite_service, "entrees_pour_formation", lambda _: [])
    result = run(executer_commande_vocale(
        ExecutionVocaleRequest(
            action="generer_formulaires",
            confirmer=True,
            session_info={"session_id": "S1", "formation_code": "IA"},
        ),
        principal=None,
    ))
    assert result.success is False
    assert result.etat == "prerequis_manquant"
