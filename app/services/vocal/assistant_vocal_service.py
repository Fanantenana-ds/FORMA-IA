"""Orchestration sûre entre le routeur vocal, C3/RAG et le frontend.

Le service ne crée ni session ni document : il prépare une action à vérifier.
Les dépendances externes sont uniquement appelées en production. Les tests les
remplacent par des doublures locales.
"""

from __future__ import annotations

import re
import asyncio
import os
import unicodedata
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
    "generer_formulaires",
    "analyser_niveaux",
    "analyser_satisfaction",
    "analyser_presences",
    "preparer_formation",
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


def _normaliser_session(value: Any) -> str:
    raw = unicodedata.normalize("NFKD", str(value or "").casefold())
    return " ".join("".join(char for char in raw if not unicodedata.combining(char)).split())


def _resoudre_session(
    intention: str,
    parametres: dict[str, Any],
    sessions: list[dict[str, Any]],
) -> tuple[dict[str, Any], str | None]:
    """Lie une commande à une session fournie par l'interface, sans deviner."""
    requires_session = {
        "creer_seance", "generer_formulaires", "analyser_niveaux",
        "analyser_satisfaction", "analyser_presences", "generer_attestation",
    }
    if intention not in requires_session:
        return parametres, None

    session_id = str(parametres.get("session_id") or "").strip()
    label = next((
        str(parametres.get(key) or "").strip()
        for key in ("nom_formation", "session", "titre_session", "formation")
        if str(parametres.get(key) or "").strip()
    ), "")
    date_session = str(parametres.get("date_debut_session") or "").strip()

    if session_id:
        candidates = [item for item in sessions if str(item.get("id", "")) == session_id]
    elif label:
        normalized_label = _normaliser_session(label)
        candidates = [
            item for item in sessions
            if normalized_label in {
                _normaliser_session(item.get("titre")),
                _normaliser_session(item.get("code")),
            }
        ]
        if date_session:
            candidates = [
                item for item in candidates
                if date_session in {
                    str(item.get("date_debut") or ""),
                    str(item.get("dates") or ""),
                }
            ]
    else:
        candidates = []

    if len(candidates) == 1:
        chosen = candidates[0]
        resolved = {**parametres, "session_id": str(chosen["id"])}
        if chosen.get("formation_code"):
            resolved["formation_code"] = chosen["formation_code"]
        resolved.setdefault("nom_formation", chosen.get("titre", ""))
        return resolved, None

    if len(candidates) > 1:
        choices = "; ".join(
            f"{item.get('titre', 'Session sans titre')} · {item.get('date_debut') or item.get('dates') or item.get('code') or item.get('id')}"
            for item in candidates[:5]
        )
        return parametres, f"Plusieurs sessions correspondent. Précisez la date ou le code : {choices}."

    available = "; ".join(
        f"{item.get('titre', 'Session sans titre')} · {item.get('date_debut') or item.get('dates') or item.get('code') or item.get('id')}"
        for item in sessions[:5]
    )
    if not sessions:
        return parametres, "Je n'ai pas la liste des sessions disponibles. Ouvrez d'abord Sessions et Groupes, puis réessayez."
    return parametres, (
        "Je ne peux pas identifier une session exacte dans la liste accessible. "
        f"Précisez son intitulé, son code ou sa date. Sessions disponibles : {available}."
    )


class AssistantVocalService:
    async def traiter(
        self,
        texte: str,
        formations: list[str] | None = None,
        conversation_id: str | None = None,
        contexte_action: list[str] | None = None,
        sessions_disponibles: list[dict[str, Any]] | None = None,
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
        sessions = [
            {key: item.get(key) for key in ("id", "titre", "code", "date_debut", "dates", "formation_code") if item.get(key) is not None}
            for item in (sessions_disponibles or [])[:50]
            if isinstance(item, dict) and item.get("id") and item.get("titre")
        ]
        contexte_items = list((contexte_action or [])[-7:])
        if sessions:
            contexte_items.append("Sessions accessibles (ne sélectionner que par intitulé/code/date exact) : " + str(sessions[:20]))
        contexte = "\n".join(contexte_items[-8:])
        commande = f"Demande en cours et précisions de l'utilisateur :\n{contexte}\nDernière précision : {texte}" if contexte else texte
        decision = await router_commande(commande, formations or [])
        confiance = float(decision.get("confiance") or 0.0)
        intention = decision.get("intention", "hors_perimetre")
        manquants = decision.get("parametres_manquants") or []

        parametres = decision.get("parametres") or {}
        parametres_resolus, clarification = _resoudre_session(intention, parametres, sessions)
        if clarification:
            resultat = {
                "intention": intention,
                "confiance": confiance,
                "parametres": parametres,
                "parametres_manquants": ["session_id"],
                "action_frontend": None,
                "prefill": {},
                "conversation_id": conversation_id,
                "sources": [],
                "suggestions": [],
                "texte_affiche": clarification,
                "texte_a_lire": _voix_courte(clarification),
                "etat": "a_preciser",
                "niveau_preuve": "non_applicable",
                "execution_plan": None,
            }
            return resultat
        decision["parametres"] = parametres_resolus
        session_fields = {"session_id", "nom_formation", "session", "titre_session", "formation", "date_debut_session"}
        manquants = [item for item in manquants if item not in session_fields]

        required_fields: dict[str, tuple[tuple[str, ...], ...]] = {
            "creer_session": (("titre", "intitule", "nom_formation", "session"), ("date_debut", "date")),
            "creer_seance": (("date", "date_seance"), ("theme", "intitule")),
            "generer_tdr": (("client",), ("objectifs", "objectif"), ("public",), ("duree",)),
        }
        field_labels = {
            "creer_session": ("intitulé de la formation", "date de début"),
            "creer_seance": ("date de la séance", "thème de la séance"),
            "generer_tdr": ("client ou organisme", "objectifs", "public cible", "durée"),
        }
        required = required_fields.get(intention, ())
        missing_required = [
            keys[0] for keys in required
            if not any(str(parametres_resolus.get(key) or "").strip() for key in keys)
        ]
        if missing_required:
            labels = field_labels[intention]
            missing_labels = [labels[index] for index, keys in enumerate(required) if keys[0] in missing_required]
            question = "Pour préparer cette action, précisez : " + ", ".join(missing_labels) + "."
            resultat = {
                "intention": intention,
                "confiance": confiance,
                "parametres": parametres_resolus,
                "parametres_manquants": missing_required,
                "action_frontend": None,
                "prefill": {},
                "conversation_id": conversation_id,
                "sources": [],
                "suggestions": [],
                "texte_affiche": question,
                "texte_a_lire": _voix_courte(question),
                "etat": "a_preciser",
                "niveau_preuve": "non_applicable",
                "execution_plan": None,
            }
            return resultat
        if required:
            satisfied_aliases = {key for aliases in required for key in aliases}
            manquants = [item for item in manquants if item not in satisfied_aliases]

        resultat: dict[str, Any] = {
            "intention": intention,
            "confiance": confiance,
            "parametres": parametres_resolus,
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
            "execution_plan": None,
        }

        from app.services.vocal.action_plan_service import plan_for
        resultat["execution_plan"] = plan_for(intention, resultat["parametres"])

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
                "execution_plan": None,
            })
            return resultat

        if manquants:
            resultat["etat"] = "a_preciser"
            resultat["action_frontend"] = None
            resultat["execution_plan"] = None
            return resultat

        if intention in {"generer_formulaires", "generer_attestation", "preparer_formation", "relance_facture"}:
            from app.services.vocal.prerequisite_service import verifier_action

            parametres = resultat["parametres"]
            contexte_resultat = {
                "reponses_disponibles": parametres.get("reponses_disponibles")
                or parametres.get("responses_disponibles")
                or False,
                "projet_id": parametres.get("projet_id"),
                "dates_formation": parametres.get("dates_formation") or (parametres.get("date_debut") and parametres.get("date_fin")),
                "participants": parametres.get("participants") or parametres.get("nombre_participants"),
                "facture_id": parametres.get("facture_id"),
                # Les participants éligibles doivent venir d'une lecture métier vérifiée,
                # jamais d'un champ proposé par le LLM.
                "participants_eligibles": False,
            }
            prerequis = verifier_action(
                intention,
                formation_code=formation_code or parametres.get("formation_code"),
                session_id=parametres.get("session_id") or parametres.get("id_session"),
                contexte=contexte_resultat,
            )
            if not prerequis.ok:
                resultat.update(
                    etat="prerequis_manquant",
                    action_frontend=prerequis.redirect_action,
                    execution_demandee=bool(prerequis.redirect_action),
                    parametres_manquants=prerequis.missing,
                    texte_affiche=prerequis.message,
                    texte_a_lire=_voix_courte(prerequis.message),
                    suggestions=[
                        "Ouvrir la base documentaire",
                        "Afficher les sessions disponibles",
                    ],
                )
                resultat["execution_plan"] = None
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
            resultat.update(
                etat="action_a_executer",
                execution_demandee=True,
                prefill={**resultat["prefill"], **resultat["parametres"]},
                texte_affiche=(
                    "Je vérifie les prérequis et j'ouvre l'écran de traitement. "
                    "La validation humaine restera nécessaire avant toute diffusion."
                ),
                texte_a_lire="Je vérifie les prérequis et j'ouvre l'écran de traitement.",
            )

        if intention in {"veille_marche", "afficher_opportunites", "afficher_sessions", "afficher_validations"}:
            resultat["texte_affiche"] = (
                "Vous pouvez consulter l'écran métier. Cette réponse vocale ne contient pas de données métier vérifiées."
            )
            resultat["texte_a_lire"] = resultat["texte_affiche"]
            resultat.update(etat="action_a_executer", execution_demandee=True,
                            texte_affiche="Je lance la détection dans l'écran de veille." if intention == "veille_marche" else "J'ouvre l'écran demandé.")

        return resultat

    async def _repondre_rag(self, question: str, resultat: dict[str, Any]) -> dict[str, Any]:
        timeout_s = max(5.0, float(os.getenv("VOCAL_RAG_TIMEOUT_S", "18")))
        try:
            reponse = await asyncio.wait_for(
                get_chat_orchestrator().traiter_message(
                    question,
                    conversation_id=resultat["conversation_id"],
                    **({"formation_code": resultat["parametres"]["formation_code"]} if resultat["parametres"].get("formation_code") else {}),
                ),
                timeout=timeout_s,
            )
        except TimeoutError:
            message = "La recherche documentaire prend trop de temps. Reformulez avec le nom de la formation ou du support."
            resultat.update(
                action_frontend="ouvrir_chat_rag",
                texte_affiche=message,
                texte_a_lire=message,
                etat="delai_depasse",
                niveau_preuve="sans_source",
            )
            return resultat
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
