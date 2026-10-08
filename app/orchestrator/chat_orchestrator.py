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


async def _appeler_llm_json(
    nom_prompt: str, contenu: str, temperature: float = 0.3
) -> Optional[Dict[str, Any]]:
    import json
    try:
        llm = get_llm_provider()
    except LLMNotAvailableError:
        return None
    try:
        reponse = await llm.generate_with_retry(
            system_prompt=_charger_prompt(nom_prompt),
            user_prompt=contenu,
            temperature=temperature, max_tokens=2000, json_mode=True, max_retries=2,
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
                texte, sources, modele_requete, cache_utilise = await self._repondre_synthese_thematique(message, conv)
            elif type_detecte == "localisation":
                texte, sources, modele_requete, cache_utilise = await self._repondre_localisation(message)
            elif type_detecte == "question_fond":
                texte, sources, modele_requete, cache_utilise = await self._repondre_question_fond(message, conv)
            elif type_detecte == "aide_plateforme":
                texte, sources, modele_requete, cache_utilise = await self._repondre_aide_plateforme(message)
            elif type_detecte == "conversationnel":
                texte, sources = self._repondre_conversationnel(message)
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

        suggestions = await self._suggestions_dynamiques(type_detecte, message, texte)

        return {
            "conversation_id": conversation_id,
            "type_reponse": type_detecte,
            "reponse": texte,
            "sources": sources,
            "formation_resolue": formation_resolue or conv.derniere_formation_code,
            "suggestions": suggestions,
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

    def _repondre_conversationnel(self, message: str = ""):
        msg = message.lower()
        # Questions d'identité → réponse spécifique FORMA-IA / ALTIORA
        if any(mot in msg for mot in ("créé", "cree", "crée", "créateur", "qui es-tu", "qui es tu",
                                      "qui t'a", "qui ta", "who are you", "c'est quoi", "c'est qui",
                                      "développé", "developpé", "développe", "construit", "fait par")):
            texte = (
                "Je suis **FORMA-IA**, l'assistant documentaire intelligent de la plateforme ALTIORA. "
                "J'ai été conçu et développé par l'équipe ALTIORA pour aider les directeurs, "
                "formateurs et assistants à accéder rapidement aux contenus de formation, "
                "aux supports indexés et aux informations de la plateforme. "
                "Comment puis-je vous aider aujourd'hui ?"
            )
        # Questions sur les capacités / ce que l'assistant peut faire
        elif any(mot in msg for mot in ("peux-tu", "peuxtu", "peux tu", "capable", "fonctionnalité",
                                        "fonctionnalite", "que sais-tu", "que fais-tu", "comment tu",
                                        "à quoi", "a quoi")):
            texte = (
                "Je peux vous aider sur plusieurs sujets :\n\n"
                "- **Catalogue des formations** : lister toutes les formations ALTIORA disponibles\n"
                "- **Contenu d'une formation** : décrire les supports et modules d'une formation précise\n"
                "- **Localisation d'un sujet** : trouver dans quel support et à quelle page un sujet est traité\n"
                "- **Synthèse thématique** : comparer plusieurs formations sur un même thème\n"
                "- **Questions de fond** : répondre à une question précise à partir des documents indexés\n"
                "- **Aide sur la plateforme** : expliquer comment utiliser les modules de FORMA-IA\n\n"
                "Que souhaitez-vous savoir ?"
            )
        else:
            # Accueil générique pour salutations, remerciements, etc.
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

    async def _repondre_synthese_thematique(self, message, conv=None):
        cache_avant = await self._cache_utilise_pour(message)
        provider = get_embedding_provider()

        resultats = await recherche.rechercher(
            message, collection="resume_formation", top_k=5,
            attente_max_s=ATTENTE_MAX_CHAT_S, repository=self.repository,
        )

        if not resultats:
            historique = ""
            if conv and hasattr(conv, "echanges") and conv.echanges:
                historique = "\n".join(
                    f"{getattr(e, 'role', '')}: {getattr(e, 'texte', '')}"
                    for e in conv.echanges[-10:]
                )
            import json as _json
            prompt_sys = (
                "Tu es FORMA-IA, l'assistant documentaire d'ALTIORA. "
                "Réponds à la question de synthèse thématique en t'appuyant sur le contexte "
                "de la conversation et ta connaissance des formations ALTIORA (IA, management, "
                "gestion de projet, compétences numériques). "
                "Zéro route HTTP. Retourne UNIQUEMENT {\"reponse\": \"...\"}."
            )
            user_msg = (f"Historique :\n{historique}\n\nQuestion : {message}"
                        if historique else f"Question : {message}")
            try:
                llm = get_llm_provider()
                rep = await llm.generate_with_retry(
                    system_prompt=prompt_sys,
                    user_prompt=user_msg,
                    temperature=0.5, max_tokens=600, json_mode=True, max_retries=1,
                    reasoning_effort="low",
                )
                data = _json.loads(rep["content"])
                texte = data.get("reponse", "")
            except Exception:
                texte = ""
            if not texte:
                return _reponse_mode_strict(), [], provider.modele_requete, cache_avant
            return texte, [], provider.modele_requete, cache_avant

        contexte = "\n\n".join(f"Formation : {r.formation_titre}\nRésumé : {r.contenu}" for r in resultats)
        resultat = await _appeler_llm_json("reponse_synthese_thematique.yaml", contexte, temperature=0.5)

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

    async def _repondre_question_fond(self, message, conv=None):
        cache_avant = await self._cache_utilise_pour(message)
        provider = get_embedding_provider()

        resultats = await recherche.rechercher(
            message, collection="support", top_k=8,
            attente_max_s=ATTENTE_MAX_CHAT_S, repository=self.repository,
        )

        if not resultats:
            # Aucun résultat RAG → LLM avec contexte de conversation
            # (gère les références anaphoriques : "cette support", "expliquer ça", etc.)
            historique = ""
            if conv and hasattr(conv, "echanges") and conv.echanges:
                historique = "\n".join(
                    f"{getattr(e, 'role', '')}: {getattr(e, 'texte', '')}"
                    for e in conv.echanges[-10:]
                )
            import json as _json
            prompt_sys = (
                "Tu es FORMA-IA, l'assistant documentaire d'ALTIORA Solutions. "
                "Réponds à la question en te basant sur le contexte de la conversation fourni. "
                "Si la question fait référence à des documents ou supports listés juste avant, "
                "explique leur contenu global (guides de la plateforme : Veille marché, TDR, "
                "Offres, Préparation, Formations M5, Attestations, Facturation, Validation HITL, "
                "Base de connaissances). "
                "Zéro route HTTP, zéro code technique. "
                'Retourne UNIQUEMENT {"reponse": "..."}.'
            )
            user_msg = (f"Historique de la conversation :\n{historique}\n\nQuestion : {message}"
                        if historique else f"Question : {message}")
            try:
                llm = get_llm_provider()
                rep = await llm.generate_with_retry(
                    system_prompt=prompt_sys,
                    user_prompt=user_msg,
                    temperature=0.5, max_tokens=600, json_mode=True, max_retries=1,
                    reasoning_effort="low",
                )
                data = _json.loads(rep["content"])
                texte = data.get("reponse", "")
            except Exception:
                texte = ""
            if not texte:
                return _reponse_mode_strict(), [], provider.modele_requete, cache_avant
            return texte, [], provider.modele_requete, cache_avant

        contexte = "\n\n".join(
            f"[{r.fichier}, p. {r.page_debut}]\n{r.contenu}" for r in resultats
        )
        resultat = await _appeler_llm_json(
            "reponse_question_fond.yaml",
            f"QUESTION : {message}\n\nEXTRAITS :\n{contexte}",
            temperature=0.5,
        )

        texte = resultat["reponse"] if resultat and resultat.get("reponse") else _reponse_mode_strict()
        sources = [
            {"fichier": r.fichier, "formation": r.formation_titre, "page": r.page_debut, "score": r.score}
            for r in resultats
        ]
        return texte, sources, provider.modele_requete, cache_avant

    async def _repondre_aide_plateforme(self, message):
        cache_avant = await self._cache_utilise_pour(message)
        provider = get_embedding_provider()

        # Seuil abaissé à 0.35 : les formulations naturelles sans "FORMA-IA"
        # dans la phrase donnent des scores entre 0.35 et 0.50 sur nos guides.
        resultats = await recherche.rechercher(
            message, collection="aide_plateforme", top_k=5, seuil_min=0.35,
            attente_max_s=ATTENTE_MAX_CHAT_S, repository=self.repository,
        )

        if not resultats:
            # Pas de résultat RAG → le LLM répond à partir de sa connaissance
            # de la plateforme (modules, workflow) sans inventer de procédure.
            prompt_fallback = (
                "Tu es FORMA-IA, l'assistant de la plateforme ALTIORA. "
                "Réponds à la question sur l'utilisation de la plateforme en décrivant "
                "les modules concernés (Veille marché, Termes de référence, Offres M3, "
                "Préparation, Gestion des formations M5, Base de connaissances RAG). "
                "Utilise un langage naturel adapté à un directeur ou formateur. "
                "Zéro route HTTP, zéro code technique. "
                'Retourne UNIQUEMENT {"reponse": "..."}.'
            )
            import json as _json
            try:
                llm = get_llm_provider()
                rep = await llm.generate_with_retry(
                    system_prompt=prompt_fallback,
                    user_prompt=f"Question : {message}",
                    temperature=0.5, max_tokens=600, json_mode=True, max_retries=1,
                    reasoning_effort="low",
                )
                data = _json.loads(rep["content"])
                texte = data.get("reponse", "")
            except Exception:
                texte = ""
            if not texte:
                texte = (
                    "La plateforme **FORMA-IA** comporte plusieurs modules : "
                    "Veille marché, Termes de référence, Offres commerciales, "
                    "Préparation, Gestion des formations et Base de connaissances. "
                    "Posez-moi une question précise sur l'un de ces modules et je vous guiderai."
                )
            return texte, [], provider.modele_requete, cache_avant

        # RAG + LLM : on synthétise les extraits avec une température plus haute
        # pour une prose plus fluide et naturelle.
        contexte = "\n\n".join(f"[{r.fichier}]\n{r.contenu}" for r in resultats)
        resultat = await _appeler_llm_json(
            "reponse_aide_plateforme.yaml",
            f"QUESTION : {message}\n\nEXTRAITS DU GUIDE :\n{contexte}",
            temperature=0.5,
        )

        if resultat and resultat.get("reponse"):
            texte = resultat["reponse"]
        else:
            # Fallback lisible si le LLM échoue : résumé des extraits trouvés
            lignes = [f"**{r.fichier}** : {r.contenu[:200]}…" for r in resultats[:3]]
            texte = "Voici ce que j'ai trouvé dans le guide :\n\n" + "\n\n".join(lignes)

        sources = [{"fichier": r.fichier, "formation": None, "page": r.page_debut, "score": r.score} for r in resultats]
        return texte, sources, provider.modele_requete, cache_avant

    # ========================================================
    # SUGGESTIONS DE RELANCE — dynamiques (LLM) + gabarit statique
    # ========================================================

    _GABARITS_SUGGESTIONS = {
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

    @staticmethod
    def _suggestions(type_detecte: str) -> List[str]:
        return ChatOrchestrator._GABARITS_SUGGESTIONS.get(type_detecte, [])[:3]

    @staticmethod
    async def _suggestions_dynamiques(
        type_detecte: str, message: str, reponse: str
    ) -> List[str]:
        """Génère 2 suggestions de relance contextuelles via LLM.
        Retombe sur le gabarit statique si le LLM échoue ou est trop lent."""
        import json as _json
        import asyncio
        if type_detecte in ("hors_sujet", "inventaire", "catalogue", "conversationnel"):
            return ChatOrchestrator._GABARITS_SUGGESTIONS.get(type_detecte, [])[:2]
        prompt_sys = (
            "Tu es FORMA-IA. À partir de la question de l'utilisateur et de ta réponse, "
            "propose 2 questions de suivi naturelles et utiles (en français, 6 à 10 mots chacune). "
            'Retourne UNIQUEMENT {"suggestions": ["question 1", "question 2"]}.'
        )
        user_msg = f"Question : {message}\nRéponse : {reponse[:300]}"
        try:
            llm = get_llm_provider()
            rep = await asyncio.wait_for(
                llm.generate_with_retry(
                    system_prompt=prompt_sys,
                    user_prompt=user_msg,
                    temperature=0.4, max_tokens=120, json_mode=True, max_retries=1,
                    reasoning_effort="low",
                ),
                timeout=3.0,
            )
            data = _json.loads(rep["content"])
            sugg = data.get("suggestions", [])
            if isinstance(sugg, list) and len(sugg) >= 1:
                return [str(s) for s in sugg[:2]]
        except Exception:
            pass
        return ChatOrchestrator._GABARITS_SUGGESTIONS.get(type_detecte, [])[:2]


_orchestrateur_instance: Optional[ChatOrchestrator] = None


def get_chat_orchestrator() -> ChatOrchestrator:
    global _orchestrateur_instance
    if _orchestrateur_instance is None:
        _orchestrateur_instance = ChatOrchestrator()
    return _orchestrateur_instance
