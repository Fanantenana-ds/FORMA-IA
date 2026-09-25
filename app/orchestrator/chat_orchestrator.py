# app/orchestrator/chat_orchestrator.py
# ============================================================
# ORCHESTRATEUR — Assistant documentaire / chat (RAG, Étape E)
# ============================================================
# Route chaque message vers l'un des 9 types (voir type_detection_service),
# MODE STRICT partout (jamais de connaissances générales), jamais plus de
# 5 s d'attente Voyage pendant le chat, mémoire de conversation, journal.
# ============================================================

import logging
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

from app.services.llm import get_llm_provider, LLMNotAvailableError
from app.services.rag import catalogue_service as catalogue
from app.services.rag import registry_service as registre
from app.services.rag import recherche_service as recherche
from app.services.rag import conversation_service as memoire
from app.services.rag import chat_log_service as journal
from app.services.rag.formation_resolver_service import resoudre_formation
from app.services.rag.type_detection_service import detecter_type
from app.services.rag.knowledge_repository import KnowledgeRepository
from app.services.rag.rate_limiter import DelaiDepasseError
from app.services.rag.embedding_provider import get_embedding_provider

logger = logging.getLogger(__name__)

_DOSSIER_PROMPTS = Path(__file__).resolve().parents[1] / "prompts" / "rag"
MENTION_FIXE = "\n\n*Réponse générée à partir des documents indexés.*"
ATTENTE_MAX_CHAT_S = 5.0


def _charger_prompt(nom_fichier: str) -> str:
    with open(_DOSSIER_PROMPTS / nom_fichier, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    sections = [data.get(cle, "") for cle in ("role", "tache", "format", "contraintes", "exemples")]
    return "\n\n".join(s for s in sections if s)


async def _appeler_llm_json(nom_prompt: str, contenu: str) -> Optional[Dict[str, Any]]:
    import json
    try:
        llm = get_llm_provider()
    except LLMNotAvailableError:
        return None
    try:
        reponse = await llm.generate_with_retry(
            system_prompt=_charger_prompt(nom_prompt),
            user_prompt=contenu,
            temperature=0.3, max_tokens=2000, json_mode=True, max_retries=2,
            # Modèle de raisonnement Groq : voir resume_service.py pour le détail.
            reasoning_effort="low",
        )
        return json.loads(reponse["content"])
    except Exception as exc:
        logger.warning(f"⚠️ Chat : appel LLM échoué ({nom_prompt}) : {type(exc).__name__} — {exc}")
        return None


def _reponse_mode_strict(suggestion_texte: str = "") -> str:
    formations = catalogue.charger_catalogue()
    liste = "\n".join(f"- {f.titre}" for f in formations) or "(aucune formation au catalogue)"
    base = "Aucun support ALTIORA ne traite ce sujet."
    if suggestion_texte:
        base += f" {suggestion_texte}"
    return f"{base}\n\nFormations disponibles :\n{liste}"


class ChatOrchestrator:
    def __init__(self, repository: Optional[KnowledgeRepository] = None):
        self.repository = repository or KnowledgeRepository()

    # ========================================================
    # POINT D'ENTRÉE
    # ========================================================

    async def traiter_message(
        self, message: str, conversation_id: Optional[str] = None,
        formation_code: Optional[str] = None,
    ) -> Dict[str, Any]:
        debut = time.perf_counter()
        conversation_id = conversation_id or memoire.nouveau_id()
        conv = memoire.charger_conversation(conversation_id)

        type_detecte = await detecter_type(message)

        modele_requete = None
        cache_utilise = None
        formation_resolue: Optional[str] = None
        statut = "ok"

        try:
            if type_detecte == "catalogue":
                texte, sources = await self._repondre_catalogue()
            elif type_detecte == "inventaire":
                texte, sources = await self._repondre_inventaire()
            elif type_detecte == "contenu_formation":
                texte, sources, formation_resolue = await self._repondre_contenu_formation(message, formation_code, conv)
            elif type_detecte == "synthese_thematique":
                texte, sources, modele_requete, cache_utilise = await self._repondre_synthese_thematique(message)
            elif type_detecte == "localisation":
                texte, sources, modele_requete, cache_utilise = await self._repondre_localisation(message)
            elif type_detecte == "question_fond":
                texte, sources, modele_requete, cache_utilise = await self._repondre_question_fond(message)
            elif type_detecte == "aide_plateforme":
                texte, sources, modele_requete, cache_utilise = await self._repondre_aide_plateforme(message)
            elif type_detecte == "conversationnel":
                texte, sources = self._repondre_conversationnel()
            else:  # hors_sujet
                texte, sources = _reponse_mode_strict(), []
        except DelaiDepasseError as exc:
            texte = f"Limite de débit Voyage atteinte, réessayez dans {exc.temps_restant_s:.0f} s."
            sources = []
            statut = "limite_debit"

        if type_detecte != "hors_sujet" and sources:
            texte += MENTION_FIXE

        duree_ms = (time.perf_counter() - debut) * 1000

        conv = memoire.ajouter_echange(conv, "utilisateur", message)
        conv = memoire.ajouter_echange(conv, "assistant", texte, formation_code=formation_resolue)
        memoire.sauvegarder_conversation(conv)

        journal.enregistrer(
            question=message, type_detecte=type_detecte,
            formation_code=formation_resolue or conv.derniere_formation_code,
            nb_sources=len(sources), modele_requete=modele_requete,
            cache_utilise=bool(cache_utilise), duree_ms=duree_ms, statut=statut,
        )

        return {
            "conversation_id": conversation_id,
            "type_reponse": type_detecte,
            "reponse": texte,
            "sources": sources,
            "formation_resolue": formation_resolue or conv.derniere_formation_code,
            "suggestions": self._suggestions(type_detecte),
            "duree_ms": round(duree_ms, 1),
        }

    # ========================================================
    # HANDLERS — sans Voyage, sans LLM
    # ========================================================

    async def _repondre_catalogue(self):
        formations = catalogue.charger_catalogue()
        if not formations:
            return "Aucune formation au catalogue pour l'instant.", []
        lignes = [
            f"- **{f.titre}** ({f.code}) — {f.duree_jours or '?'} jour(s), domaine : {f.domaine or 'non précisé'}"
            for f in formations
        ]
        return "Voici les formations disponibles :\n\n" + "\n".join(lignes), []

    async def _repondre_inventaire(self):
        entrees = list(registre.charger_registre().values())
        indexees = [e for e in entrees if e.statut == "indexe"]
        if not indexees:
            return "Aucun document indexé pour l'instant.", []
        lignes = [f"- {e.fichier} ({e.formation_code or 'sans formation'}) — {e.nb_chunks} chunk(s)" for e in indexees]
        return f"{len(indexees)} document(s) indexé(s) :\n\n" + "\n".join(lignes), []

    def _repondre_conversationnel(self):
        # Python d'abord (mission) : gabarit fixe, pas d'appel LLM pour un
        # simple message d'accueil/remerciement.
        texte = (
            "Bonjour ! Je suis l'assistant documentaire de FORMA-IA. "
            "Je peux vous renseigner sur les formations ALTIORA (contenu, "
            "supports, où un sujet est expliqué), vous donner le catalogue "
            "ou l'inventaire des documents indexés, ou vous aider sur "
            "l'utilisation de la plateforme. Que puis-je faire pour vous ?"
        )
        return texte, []

    # ========================================================
    # HANDLERS — avec formation résolue (mémoire, sans Voyage, LLM oui)
    # ========================================================

    async def _repondre_contenu_formation(self, message, formation_code_force, conv):
        resolution = None
        if formation_code_force:
            resolution_formation = catalogue.obtenir_formation(formation_code_force)
            if resolution_formation:
                resolution = type("R", (), {"statut": "trouvee", "formation": resolution_formation})()

        if resolution is None:
            resolution = resoudre_formation(message)

        if resolution.statut == "aucune" and conv.derniere_formation_code:
            formation_memorisee = catalogue.obtenir_formation(conv.derniere_formation_code)
            if formation_memorisee:
                resolution = type("R", (), {"statut": "trouvee", "formation": formation_memorisee})()

        if resolution.statut == "ambigue":
            noms = ", ".join(f.titre for f in resolution.candidats[:5])
            return f"Plusieurs formations correspondent : {noms}. Laquelle voulez-vous dire ?", [], None

        if resolution.statut == "aucune":
            liste = ", ".join(f.titre for f in catalogue.charger_catalogue()[:10])
            return f"Je ne reconnais pas cette formation. Formations disponibles : {liste}.", [], None

        formation = resolution.formation
        entrees = [e for e in registre.entrees_pour_formation(formation.code) if e.statut == "indexe"]

        if not entrees:
            return f"Aucun support indexé pour la formation « {formation.titre} » pour l'instant.", [], formation.code

        contexte = "\n\n".join(
            f"Support : {e.fichier}\nRésumé : {e.resume or 'non disponible'}\nPlan : {e.plan or 'non disponible'}"
            for e in entrees
        )
        resultat = await _appeler_llm_json("reponse_contenu_formation.yaml", f"Formation : {formation.titre}\n\n{contexte}")

        if resultat and resultat.get("reponse"):
            texte = resultat["reponse"]
        else:
            texte = f"La formation **{formation.titre}** comprend {len(entrees)} support(s) :\n\n" + "\n".join(
                f"- {e.fichier} : {e.resume or 'résumé non disponible'}" for e in entrees
            )

        sources = [{"fichier": e.fichier, "formation": formation.titre, "page": None, "score": None} for e in entrees]
        return texte, sources, formation.code

    # ========================================================
    # HANDLERS — avec Voyage (recherche vectorielle)
    # ========================================================

    async def _cache_utilise_pour(self, texte: str) -> bool:
        from app.services.rag.query_cache_service import depuis_cache
        provider = get_embedding_provider()
        return depuis_cache(texte, provider.modele_requete) is not None

    async def _repondre_synthese_thematique(self, message):
        cache_avant = await self._cache_utilise_pour(message)
        provider = get_embedding_provider()

        resultats = await recherche.rechercher(
            message, collection="resume_formation", top_k=5,
            attente_max_s=ATTENTE_MAX_CHAT_S, repository=self.repository,
        )

        if not resultats:
            return _reponse_mode_strict(), [], provider.modele_requete, cache_avant

        contexte = "\n\n".join(f"Formation : {r.formation_titre}\nRésumé : {r.contenu}" for r in resultats)
        resultat = await _appeler_llm_json("reponse_synthese_thematique.yaml", contexte)

        texte = resultat["reponse"] if resultat and resultat.get("reponse") else _reponse_mode_strict()
        sources = [{"fichier": None, "formation": r.formation_titre, "page": None, "score": r.score} for r in resultats]
        return texte, sources, provider.modele_requete, cache_avant

    async def _repondre_localisation(self, message):
        cache_avant = await self._cache_utilise_pour(message)
        provider = get_embedding_provider()

        resultats = await recherche.rechercher(
            message, collection="support", top_k=8,
            attente_max_s=ATTENTE_MAX_CHAT_S, repository=self.repository,
        )

        if not resultats:
            return _reponse_mode_strict(), [], provider.modele_requete, cache_avant

        # Groupé par fichier (mission §"localisation")
        par_fichier: Dict[str, List] = {}
        for r in resultats:
            par_fichier.setdefault(r.fichier, []).append(r)

        lignes = []
        sources = []
        for fichier, occurrences in par_fichier.items():
            meilleur = max(occurrences, key=lambda r: r.score)
            pages = sorted({o.page_debut for o in occurrences if o.page_debut})
            plage = f"{min(pages)} à {max(pages)}" if len(pages) > 1 else (str(pages[0]) if pages else "?")
            lignes.append(f"- **{fichier}** — {meilleur.formation_titre or ''} — pages {plage} : « {meilleur.contenu[:150]}… »")
            sources.append({
                "fichier": fichier, "formation": meilleur.formation_titre,
                "page": meilleur.page_debut, "score": meilleur.score,
            })

        texte = "Voici où ce sujet est expliqué :\n\n" + "\n".join(lignes)
        return texte, sources, provider.modele_requete, cache_avant

    async def _repondre_question_fond(self, message):
        cache_avant = await self._cache_utilise_pour(message)
        provider = get_embedding_provider()

        resultats = await recherche.rechercher(
            message, collection="support", top_k=8,
            attente_max_s=ATTENTE_MAX_CHAT_S, repository=self.repository,
        )

        if not resultats:
            return _reponse_mode_strict(), [], provider.modele_requete, cache_avant

        contexte = "\n\n".join(
            f"[{r.fichier}, p. {r.page_debut}]\n{r.contenu}" for r in resultats
        )
        resultat = await _appeler_llm_json("reponse_question_fond.yaml", f"QUESTION : {message}\n\nEXTRAITS :\n{contexte}")

        texte = resultat["reponse"] if resultat and resultat.get("reponse") else _reponse_mode_strict()
        sources = [
            {"fichier": r.fichier, "formation": r.formation_titre, "page": r.page_debut, "score": r.score}
            for r in resultats
        ]
        return texte, sources, provider.modele_requete, cache_avant

    async def _repondre_aide_plateforme(self, message):
        cache_avant = await self._cache_utilise_pour(message)
        provider = get_embedding_provider()

        resultats = await recherche.rechercher(
            message, collection="aide_plateforme", top_k=5,
            attente_max_s=ATTENTE_MAX_CHAT_S, repository=self.repository,
        )

        if not resultats:
            return _reponse_mode_strict(
                "Le guide utilisateur n'a peut-être pas encore été indexé (Étape F)."
            ), [], provider.modele_requete, cache_avant

        contexte = "\n\n".join(f"[{r.fichier}]\n{r.contenu}" for r in resultats)
        resultat = await _appeler_llm_json("reponse_aide_plateforme.yaml", f"QUESTION : {message}\n\nEXTRAITS :\n{contexte}")

        texte = resultat["reponse"] if resultat and resultat.get("reponse") else _reponse_mode_strict()
        sources = [{"fichier": r.fichier, "formation": None, "page": r.page_debut, "score": r.score} for r in resultats]
        return texte, sources, provider.modele_requete, cache_avant

    # ========================================================
    # SUGGESTIONS DE RELANCE (2-3, gabarit par type)
    # ========================================================

    @staticmethod
    def _suggestions(type_detecte: str) -> List[str]:
        gabarits = {
            "catalogue": ["Voir le contenu d'une formation précise", "Combien de supports sont indexés ?"],
            "inventaire": ["Voir le catalogue des formations"],
            "contenu_formation": ["Où est expliqué un sujet précis dans cette formation ?", "Et le module suivant ?"],
            "synthese_thematique": ["Voir le contenu détaillé d'une de ces formations"],
            "localisation": ["Poser une question précise sur ce sujet"],
            "question_fond": ["Où est-ce expliqué exactement ?", "Voir le contenu complet de cette formation"],
            "aide_plateforme": ["Poser une autre question sur la plateforme"],
            "conversationnel": ["Voir le catalogue des formations", "Poser une question sur un support"],
            "hors_sujet": ["Voir le catalogue des formations disponibles"],
        }
        return gabarits.get(type_detecte, [])[:3]


_orchestrateur_instance: Optional[ChatOrchestrator] = None


def get_chat_orchestrator() -> ChatOrchestrator:
    global _orchestrateur_instance
    if _orchestrateur_instance is None:
        _orchestrateur_instance = ChatOrchestrator()
    return _orchestrateur_instance
