"""Plans d'exécution déclaratifs pour l'Agent Vocal.

Le plan décrit l'action à transmettre au frontend et au service métier. Il ne
déclenche aucune mutation : les opérations externes restent soumises au HITL
ou à la confirmation explicite de l'utilisateur.
"""

from __future__ import annotations

from typing import Any


PLANS: dict[str, dict[str, Any]] = {
    "generer_formulaires": {
        "action_frontend": "ouvrir_formulaires_session",
        "module": "M5",
        "endpoint": "/api/v1/ia/formations/generate-forms",
        "method": "POST",
        "requires_human_confirmation": True,
        "hitl_agent": "agent_1_forms",
        "preconditions": ["session_id", "formation_code", "support_rag_indexe"],
    },
    "analyser_niveaux": {
        "action_frontend": "ouvrir_analyse_niveaux",
        "module": "M5",
        "endpoint": "/api/v1/ia/formations/analyze-levels",
        "method": "POST",
        "requires_human_confirmation": False,
        "preconditions": ["session_id", "reponses_google_forms"],
    },
    "analyser_satisfaction": {
        "action_frontend": "ouvrir_analyse_satisfaction",
        "module": "M5",
        "endpoint": "/api/v1/ia/formations/analyze-satisfaction",
        "method": "POST",
        "requires_human_confirmation": False,
        "preconditions": ["session_id", "reponses_google_forms"],
    },
    "analyser_presences": {
        "action_frontend": "ouvrir_analyse_presences",
        "module": "M5",
        "endpoint": "/api/v1/ia/formations/analyze-presences",
        "method": "POST",
        "requires_human_confirmation": False,
        "preconditions": ["session_id", "presences_session"],
    },
    "generer_attestation": {
        "action_frontend": "ouvrir_formulaire_attestation",
        "module": "M6",
        "endpoint": "/api/v1/ia/formations/generate-attestations",
        "method": "POST",
        "requires_human_confirmation": True,
        "hitl_agent": "agent_5_attestations",
        "preconditions": ["session_id", "eligibilite_presences"],
    },
    "preparer_formation": {
        "action_frontend": "ouvrir_preparation",
        "module": "Preparation",
        "endpoint": "/api/v1/ia/preparation/preparer",
        "method": "POST",
        "requires_human_confirmation": True,
        "preconditions": ["projet_id", "dates_formation", "participants"],
    },
    "relance_facture": {
        "action_frontend": "ouvrir_facturation",
        "module": "M7",
        "endpoint": "/api/v1/ia/facturation/relances/generer",
        "method": "POST",
        "requires_human_confirmation": True,
        "hitl_agent": "agent_m7_relance",
        "preconditions": ["facture_id", "facture_en_retard"],
    },
}


def plan_for(intention: str, parameters: dict[str, Any] | None = None) -> dict[str, Any] | None:
    plan = PLANS.get(intention)
    if not plan:
        return None
    result = dict(plan)
    result["parameters"] = dict(parameters or {})
    return result
