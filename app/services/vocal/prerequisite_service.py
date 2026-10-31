"""Vérification locale des prérequis des actions vocales.

Ce service ne déclenche aucune mutation et ne remplace pas les contrôles
Backend. Il permet au routeur vocal de refuser proprement une action dont le
contexte pédagogique ou opérationnel n'est pas prêt.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.services.rag.registry_service import entrees_pour_formation


@dataclass(frozen=True)
class PrerequisiteResult:
    ok: bool
    missing: list[str] = field(default_factory=list)
    message: str = ""
    redirect_action: str | None = None


def _support_indexe(formation_code: str | None) -> bool:
    if not formation_code:
        return False
    return any(
        entree.collection == "support" and entree.statut == "indexe"
        for entree in entrees_pour_formation(formation_code)
    )


def verifier_action(
    intention: str,
    *,
    formation_code: str | None = None,
    session_id: str | None = None,
    contexte: dict | None = None,
) -> PrerequisiteResult:
    """Retourne un résultat explicable avant toute action vocale métier."""
    contexte = contexte or {}

    if intention == "generer_formulaires":
        missing: list[str] = []
        if not session_id:
            missing.append("session_id")
        if not formation_code:
            missing.append("formation_code")
        elif not _support_indexe(formation_code):
            return PrerequisiteResult(
                ok=False,
                missing=["support_rag_indexe"],
                message=(
                    f"Je ne peux pas générer les formulaires pour « {formation_code} » : "
                    "aucun support de cours indexé n'est disponible. "
                    "Importez et indexez d'abord le support dans la Base documentaire."
                ),
                redirect_action="ouvrir_chat_rag",
            )
        if missing:
            return PrerequisiteResult(
                ok=False,
                missing=missing,
                message="J'ai besoin de la session et de la formation exacte avant de générer les formulaires.",
            )

    if intention in {"analyser_niveaux", "analyser_satisfaction"}:
        if not session_id:
            return PrerequisiteResult(
                ok=False,
                missing=["session_id"],
                message="Précisez la session à analyser pour éviter de mélanger les réponses.",
            )
        if not contexte.get("reponses_disponibles"):
            return PrerequisiteResult(
                ok=False,
                missing=["reponses_google_forms"],
                message=(
                    "Je ne peux pas lancer cette analyse : les réponses Google Forms "
                    "de cette session ne sont pas encore disponibles."
                ),
                redirect_action="ouvrir_formulaires_session",
            )

    if intention in {"analyser_presences", "generer_attestations"} and not session_id:
        return PrerequisiteResult(
            ok=False,
            missing=["session_id"],
            message="Précisez la session concernée avant de traiter les présences ou les attestations.",
        )

    if intention == "preparer_formation" and not contexte.get("projet_id"):
        return PrerequisiteResult(
            ok=False,
            missing=["projet_id"],
            message="Précisez le projet ou l'opportunité acceptée avant de préparer la formation.",
            redirect_action="ouvrir_preparation",
        )

    return PrerequisiteResult(ok=True)
