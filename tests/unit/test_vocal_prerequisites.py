from types import SimpleNamespace

from app.services.vocal import prerequisite_service as prerequisites
from app.services.vocal.action_plan_service import plan_for


def test_generation_formulaires_refuse_si_support_non_indexe(monkeypatch):
    monkeypatch.setattr(prerequisites, "entrees_pour_formation", lambda _: [])
    result = prerequisites.verifier_action(
        "generer_formulaires", formation_code="IA_FONDAMENTAUX", session_id="S1"
    )
    assert result.ok is False
    assert "support_rag_indexe" in result.missing
    assert result.redirect_action == "ouvrir_chat_rag"


def test_generation_formulaires_acceptee_si_support_indexe(monkeypatch):
    monkeypatch.setattr(
        prerequisites,
        "entrees_pour_formation",
        lambda _: [SimpleNamespace(collection="support", statut="indexe")],
    )
    result = prerequisites.verifier_action(
        "generer_formulaires", formation_code="IA_FONDAMENTAUX", session_id="S1"
    )
    assert result.ok is True


def test_analyse_demande_les_reponses_de_la_session():
    result = prerequisites.verifier_action(
        "analyser_satisfaction", session_id="S1", contexte={"reponses_disponibles": False}
    )
    assert result.ok is False
    assert "reponses_google_forms" in result.missing


def test_plan_formulaires_decrit_endpoint_et_hitl():
    plan = plan_for("generer_formulaires", {"session_id": "S1"})
    assert plan["endpoint"].endswith("/ia/formations/generate-forms")
    assert plan["requires_human_confirmation"] is True
    assert plan["hitl_agent"] == "agent_1_forms"
