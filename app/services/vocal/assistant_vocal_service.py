"""Orchestration sûre entre le routeur vocal, C3/RAG et le frontend.

Le service ne crée ni session ni document : il prépare une action à vérifier.
Les dépendances externes sont uniquement appelées en production. Les tests les
remplacent par des doublures locales.
"""

from __future__ import annotations

import re
from typing import Any

from app.orchestrator.chat_orchestrator import get_chat_orchestrator
from app.services.vocal.routeur_vocal import router_commande


SEUIL_CONFIANCE_CONFIRMATION = 0.70
INTENTIONS_MUTABLES = {
    "creer_seance",
    "creer_session",
    "generer_tdr",
    "generer_offre",
    "generer_attestation",
    "relance_facture",
}


def _voix_courte(texte: str, maximum: int = 260) -> str:
    """Produit une synthèse orale propre, distincte du Markdown affiché.

    La synthèse vocale du navigateur lit littéralement les caractères Markdown
    tels que les astérisques. Elle ne doit donc jamais recevoir le texte de
    présentation brut, ni une réponse trop longue pour une interaction vocale.
    """
    texte = texte or ""
    texte = re.sub(r"```[\s\S]*?```", "", texte)
    texte = "\n".join(ligne for ligne in texte.splitlines() if not ligne.strip().startswith("|"))
    texte = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", texte)  # lien Markdown
    texte = re.sub(r"[`*_#>\\]", "", texte)
    texte = re.sub(r"\|", ", ", texte)
    texte = re.sub(r"\s+", " ", texte).strip()
    if not texte:
        return "Je n'ai pas de réponse courte à lire."

    # Deux phrases suffisent à l'oral. Le détail reste visible à l'écran.
    phrases = re.split(r"(?<=[.!?])\s+", texte)
    synthese = " ".join(phrases[:2]).strip()
    if len(synthese) > maximum:
        synthese = synthese[:maximum].rsplit(" ", 1)[0].rstrip(" ,;:") + "."
    return synthese


class AssistantVocalService:
    async def traiter(
        self,
        texte: str,
        formations: list[str] | None = None,
        conversation_id: str | None = None,
        contexte_action: list[str] | None = None,
        owner: str = "internal",
        ecran_actuel: str | None = None,
        formation_code: str | None = None,
    ) -> dict[str, Any]:
        from app.services.vocal.business_context_service import concerns_market_results, explain_market
        if concerns_market_results(texte, ecran_actuel):
            explanation = await explain_market(texte, owner)
            return {"intention": "question_rag", "confiance": 1.0, "parametres": {}, "prefill": {},
                    "parametres_manquants": [], "action_frontend": None, "conversation_id": conversation_id,
                    "suggestions": ["Quelle opportunité examiner en premier ?", "Pourquoi l'analyse est-elle partielle ?"], **explanation}
        contexte = "\n".join((contexte_action or [])[-8:])
        commande = f"Demande en cours et précisions de l'utilisateur :\n{contexte}\nDernière précision : {texte}" if contexte else texte
        decision = await router_commande(commande, formations or [])
        confiance = float(decision.get("confiance") or 0.0)
        intention = decision.get("intention", "hors_perimetre")
        manquants = decision.get("parametres_manquants") or []

        resultat: dict[str, Any] = {
            "intention": intention,
            "confiance": confiance,
            "parametres": decision.get("parametres") or {},
            "parametres_manquants": manquants,
            "action_frontend": decision.get("action_frontend"),
            "prefill": decision.get("prefill") or {},
            "conversation_id": conversation_id,
            "sources": [],
            "suggestions": [],
            "texte_affiche": decision.get("reponse_vocale") or "",
            "texte_a_lire": _voix_courte(decision.get("reponse_vocale") or ""),
            "etat": "pret_a_verifier",
            "niveau_preuve": "non_applicable",
        }

        # Une faible confiance doit toujours conduire à une clarification,
        # jamais à l'ouverture ou l'exécution d'une action métier.
        if confiance < SEUIL_CONFIANCE_CONFIRMATION and intention != "hors_perimetre":
            resultat.update({
                "etat": "a_preciser",
                "action_frontend": None,
                "prefill": {},
                "texte_affiche": "Je ne suis pas certain d'avoir bien compris. "
                "Pouvez-vous reformuler ou confirmer votre demande ?",
                "texte_a_lire": "Je ne suis pas certain d'avoir bien compris. Pouvez-vous reformuler ?",
            })
            return resultat

        if manquants:
            resultat["etat"] = "a_preciser"
            resultat["action_frontend"] = None
            return resultat

        if intention == "conversationnel":
            resultat.update(etat="reponse_plateforme", niveau_preuve="connaissance_plateforme")
            return resultat

        if intention == "question_rag":
            if formation_code:
                resultat["parametres"]["formation_code"] = formation_code
            return await self._repondre_rag(texte, resultat)

        if intention in {"creer_seance", "creer_session"}:
            resultat.update(
                etat="action_a_executer", execution_demandee=True,
                action_frontend="ouvrir_formulaire_session" if intention == "creer_session" else "ouvrir_formulaire_seance",
                prefill={**resultat["prefill"], **resultat["parametres"]},
                texte_affiche="Je vérifie les informations et prépare l'exécution dans l'écran des formations.",
                texte_a_lire="Je vérifie les informations de votre demande.",
            )
            return resultat

        if intention == "generer_tdr":
            resultat.update(etat="action_a_executer", execution_demandee=True,
                            action_frontend="ouvrir_formulaire_tdr",
                            prefill={**resultat["prefill"], **resultat["parametres"]},
                            texte_affiche="Je prépare la génération du brouillon TDR.")
            return resultat

        # Les actions de création/génération restent préparées : le frontend
        # ouvre l'écran correspondant, puis l'humain valide l'envoi.
        if intention in INTENTIONS_MUTABLES:
            resultat["etat"] = "integration_requise"
            resultat["action_frontend"] = None
            resultat["texte_affiche"] = (
                "Cette commande n'est pas encore reliée au service métier depuis l'assistant vocal. "
                "Aucune création ni génération n'a encore été effectuée."
            )
            resultat["texte_a_lire"] = _voix_courte(resultat["texte_affiche"])

        if intention in {"veille_marche", "afficher_opportunites", "afficher_sessions", "afficher_validations"}:
            resultat["texte_affiche"] = (
                "Vous pouvez consulter l'écran métier. Cette réponse vocale ne contient pas de données métier vérifiées."
            )
            resultat["texte_a_lire"] = resultat["texte_affiche"]
            if intention == "afficher_validations":
                resultat["action_frontend"] = None
                resultat["etat"] = "integration_requise"
            else:
                resultat.update(etat="action_a_executer", execution_demandee=True,
                                texte_affiche="Je lance la détection dans l'écran de veille." if intention == "veille_marche" else "J'ouvre l'écran demandé.")

        return resultat

    async def _repondre_rag(self, question: str, resultat: dict[str, Any]) -> dict[str, Any]:
        reponse = await get_chat_orchestrator().traiter_message(
            question,
            conversation_id=resultat["conversation_id"],
            **({"formation_code": resultat["parametres"]["formation_code"]} if resultat["parametres"].get("formation_code") else {}),
        )
        sources = reponse.get("sources") or []
        texte = reponse.get("reponse") or "Je n'ai pas trouvé de réponse exploitable."
        sourcee = bool(sources)
        from app.orchestrator.chat_orchestrator import _est_demande_generale_plateforme
        est_aide_plateforme = reponse.get("type_reponse") == "aide_plateforme" and _est_demande_generale_plateforme(question)
        if not sourcee and reponse.get("type_reponse") in {
            "question_fond", "synthese_thematique", "localisation", "contenu_formation", "aide_plateforme"
        } and not est_aide_plateforme:
            texte = "Je ne trouve pas de source documentaire suffisante. Précisez le support ou la formation concernée."
        etat = "reponse_sourcee" if sourcee else ("reponse_plateforme" if est_aide_plateforme else "reponse_sans_source")
        niveau_preuve = "sourcee" if sourcee else ("connaissance_plateforme" if est_aide_plateforme else "sans_source")
        suffixe_voix = (
            " Les sources sont affichées à l'écran. Veuillez les vérifier."
            if sourcee else
            " Je peux détailler le module de votre choix."
            if est_aide_plateforme else
            " Je ne dispose pas de source documentaire à afficher pour cette réponse."
        )
        resultat.update({
            "conversation_id": reponse.get("conversation_id"),
            "sources": sources,
            "suggestions": reponse.get("suggestions") or [],
            "action_frontend": "ouvrir_chat_rag",
            "texte_affiche": texte,
            "texte_a_lire": _voix_courte(texte) + suffixe_voix,
            "etat": etat,
            "niveau_preuve": niveau_preuve,
        })
        return resultat


_assistant_vocal: AssistantVocalService | None = None


def get_assistant_vocal_service() -> AssistantVocalService:
    global _assistant_vocal
    if _assistant_vocal is None:
        _assistant_vocal = AssistantVocalService()
    return _assistant_vocal
