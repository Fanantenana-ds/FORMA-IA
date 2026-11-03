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
from typing import Any, Awaitable, Callable, Dict, List, Optional

import yaml

from app.services.llm import LLMNotAvailableError, get_llm_provider
from app.services.rag import catalogue_service as catalogue
from app.services.rag import chat_log_service as journal
from app.services.rag import conversation_service as memoire
from app.services.rag import recherche_service as recherche
from app.services.rag import registry_service as registre
from app.services.rag import response_cache_service as rcache
from app.services.rag.embedding_provider import get_embedding_provider
from app.services.rag.formation_resolver_service import resoudre_formation
from app.services.rag.knowledge_repository import KnowledgeRepository
from app.services.rag.rate_limiter import DelaiDepasseError
from app.services.rag.type_detection_service import detecter_type

logger = logging.getLogger(__name__)

_DOSSIER_PROMPTS = Path(__file__).resolve().parents[1] / "prompts" / "rag"
MENTION_FIXE = "\n\n*Réponse générée à partir des documents indexés.*"
ATTENTE_MAX_CHAT_S = 5.0
GUIDE_DEMARRAGE_PLATEFORME = """\
**FORMA-IA** guide chaque étape du cycle de vie d'une formation, de la **détection d'une opportunité** jusqu'à la **facturation**. Les modules disponibles :

- **Étape 1 — Veille marché** : détection automatique des appels d'offres, scorés et classés par pertinence
- **Étape 2 — TDR** : génération des Termes de Référence (objectifs, profil, compétences, calendrier), soumis à **validation humaine**
- **Étape 3 — Offre technique & financière** : offre complète (méthodologie + budget), passée en **validation avant envoi**
- **Étape 4 — Préparation** : budget prévisionnel et emploi du temps (séances, horaires, intervenants)
- **Étape 5 — Sessions & groupes** : gestion des participants, **présences**, évaluations avant/après
- **Étape 6 — Attestations** : génération automatique des **attestations PDF** par participant
- **Étape 7 — Facturation** : émission des factures + **relances automatiques** soumises à validation
- **Base documentaire (RAG)** : questions sur vos supports indexés (PDF, DOCX, PPTX)
- **Validation IA (HITL)** : chaque contenu généré (TDR, offre, relance, syllabus) doit être **approuvé** avant usage

Quel module souhaitez-vous explorer en détail ?\
"""


def _est_demande_generale_plateforme(message: str) -> bool:
    """Distingue l'accueil générique d'une question métier qui mérite C3/LLM.

    Le guide local répond seulement à « comment utiliser la plateforme ? ».
    Une procédure concrète (TDR, validation, session, offre, etc.) reste traitée
    par l'agent C3, ses documents indexés et le LLM de synthèse.
    """
    normalise = " ".join(message.lower().strip().split())
    termes_metier = (
        "veille", "tdr", "termes de reference", "offre", "session", "seance",
        "formation", "validation", "valider", "hitl", "facture", "relance",
        "document", "support", "rag", "source", "index", "presence", "evaluation",
    )
    return (
        ("platform" in normalise or "plateforme" in normalise or "plate-forme" in normalise or "forma-ia" in normalise or "forma ia" in normalise)
        and not any(terme in normalise for terme in termes_metier)
    )


def _charger_prompt(nom_fichier: str) -> str:
    with open(_DOSSIER_PROMPTS / nom_fichier, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    sections = [data.get(cle, "") for cle in ("role", "tache", "format", "contraintes", "exemples")]
    return "\n\n".join(s for s in sections if s)


MAX_HISTORIQUE_ECHANGES = 6  # 3 tours utilisateur + 3 réponses assistant injectés dans le prompt


def _formater_historique(conv: "memoire.Conversation") -> str:
    """Retourne les N derniers échanges formatés pour injection dans le prompt LLM."""
    if not conv or not conv.echanges:
        return ""
    derniers = conv.echanges[-(MAX_HISTORIQUE_ECHANGES):]
    lignes = []
    for e in derniers:
        role = "Utilisateur" if e.role == "utilisateur" else "Assistant"
        lignes.append(f"{role} : {e.texte[:400]}")
    return "\n".join(lignes)


async def _appeler_llm_json(
    nom_prompt: str, contenu: str, temperature: float = 0.3,
    consigne_additionnelle: str | None = None,
    historique: str | None = None,
) -> dict[str, Any] | None:
    import json
    try:
        llm = get_llm_provider()
    except LLMNotAvailableError:
        return None
    try:
        contexte_historique = (
            f"\n\nHISTORIQUE DE LA CONVERSATION (pour contexte, ne pas répéter) :\n{historique}"
            if historique else ""
        )
        reponse = await llm.generate_with_retry(
            system_prompt=(
                _charger_prompt(nom_prompt)
                + "\n\nRÈGLE DE FIABILITÉ : utilise uniquement les informations présentes dans le contexte fourni. "
                "N'ajoute aucun fait issu de connaissances générales. Si le contexte ne suffit pas, indique clairement la limite."
                + (f"\n\n{consigne_additionnelle}" if consigne_additionnelle else "")
                + contexte_historique
            ),
            user_prompt=contenu,
            temperature=temperature, max_tokens=2000, json_mode=True, max_retries=2,
            reasoning_effort="low",
        )
        return json.loads(reponse["content"])
    except Exception as exc:
        logger.warning(f"⚠️ Chat : appel LLM échoué ({nom_prompt}) : {type(exc).__name__} — {exc}")
        return None


def _reponse_mode_strict(suggestion_texte: str = "") -> str:
    base = "Aucun support ALTIORA ne traite ce sujet."
    if suggestion_texte:
        base += f" {suggestion_texte}"
    return base


class ChatOrchestrator:
    def __init__(self, repository: KnowledgeRepository | None = None):
        self.repository = repository or KnowledgeRepository()

    # ========================================================
    # POINT D'ENTRÉE
    # ========================================================

    async def traiter_message(
        self, message: str, conversation_id: str | None = None,
        formation_code: str | None = None,
        session_id: str | None = None,
        module: str | None = None,
        allowed_formation_codes: set[str] | None = None,
        allowed_session_ids: set[str] | None = None,
        hide_references: bool = False,
        user_id: str | None = None,
        on_progress: Callable[[str, str], Awaitable[None]] | None = None,
    ) -> dict[str, Any]:
        async def progress(stage: str, label: str) -> None:
            if on_progress:
                await on_progress(stage, label)

        debut = time.perf_counter()
        conversation_id = conversation_id or memoire.nouveau_id()
        conv = memoire.charger_conversation(conversation_id)

        await progress("status", "Analyse de votre question…")
        type_detecte = await detecter_type(message, conv=conv)
        await progress("status", f"Question reconnue : {type_detecte.replace('_', ' ')}. Préparation de la recherche…")

        reponse_depuis_cache = False

        modele_requete = None
        cache_utilise = None
        formation_resolue: str | None = None
        statut = "ok"

        if type_detecte in {"synthese_thematique", "localisation", "question_fond", "aide_plateforme", "contenu_formation"}:
            await progress("status", "Recherche des passages pertinents dans les supports indexés…")
        elif type_detecte == "catalogue":
            await progress("status", "Vérification des formations qui possèdent des supports indexés…")
        elif type_detecte == "inventaire":
            await progress("status", "Comptage des supports réellement indexés…")

        try:
            if type_detecte == "catalogue":
                texte, sources = await self._repondre_catalogue(allowed_formation_codes, allowed_session_ids)
            elif type_detecte == "inventaire":
                texte, sources = await self._repondre_inventaire(allowed_formation_codes, allowed_session_ids, None, hide_references)
            elif type_detecte == "contenu_formation":
                texte, sources, formation_resolue = await self._repondre_contenu_formation(message, formation_code, session_id, module, conv, hide_references)
            elif type_detecte == "synthese_thematique":
                if allowed_session_ids is None:
                    texte, sources, modele_requete, cache_utilise = await self._repondre_synthese_thematique(message, conv, None, None, None, None, hide_references)
                else:
                    texte, sources, modele_requete, cache_utilise = await self._repondre_synthese_thematique(message, conv, formation_code, session_id, module, allowed_session_ids, hide_references)
            elif type_detecte == "localisation":
                # Les formateurs ne reçoivent pas les références de fichiers/pages.
                # Leur recherche reste strictement limitée à la session affectée.
                texte, sources, modele_requete, cache_utilise = await self._repondre_localisation(message, formation_code, session_id, module, hide_references)
            elif type_detecte == "question_fond":
                texte, sources, modele_requete, cache_utilise = await self._repondre_question_fond(message, conv, formation_code, session_id, module, hide_references)
                if cache_utilise is True and not await self._cache_utilise_pour(message):
                    reponse_depuis_cache = True
            elif type_detecte == "aide_plateforme":
                texte, sources, modele_requete, cache_utilise = await self._repondre_aide_plateforme(message, hide_references, conv=conv)
                if cache_utilise is True and not await self._cache_utilise_pour(message):
                    reponse_depuis_cache = True
            elif type_detecte == "conversationnel":
                texte, sources = await self._repondre_conversationnel(message, conv=conv)
            elif type_detecte == "incomprehensible":
                texte, sources = self._repondre_incomprehensible(message), []
            else:  # hors_sujet
                texte, sources = _reponse_mode_strict(), []
        except DelaiDepasseError as exc:
            texte = f"Limite de débit Voyage atteinte, réessayez dans {exc.temps_restant_s:.0f} s."
            sources = []
            statut = "limite_debit"

        await progress("status", "Structuration de la réponse…")

        if type_detecte not in ("hors_sujet", "incomprehensible") and sources and not hide_references:
            texte += MENTION_FIXE
        if hide_references:
            sources = []

        duree_ms = (time.perf_counter() - debut) * 1000

        if formation_code:
            formation_resolue = formation_code
        conv = memoire.ajouter_echange(conv, "utilisateur", message)
        conv = memoire.ajouter_echange(conv, "assistant", texte, formation_code=formation_resolue, type_reponse=type_detecte)
        if user_id:
            conv.user_id = user_id
        memoire.sauvegarder_conversation(conv)

        journal.enregistrer(
            question=message, type_detecte=type_detecte,
            formation_code=formation_resolue or conv.derniere_formation_code,
            nb_sources=len(sources), modele_requete=modele_requete,
            cache_utilise=bool(cache_utilise), duree_ms=duree_ms, statut=statut,
        )

        await progress("status", "Réponse préparée à partir des supports autorisés…")
        suggestions = await self._suggestions_dynamiques(type_detecte, message, texte)

        return {
            "conversation_id": conversation_id,
            "type_reponse": type_detecte,
            "reponse": texte,
            "sources": sources,
            "formation_resolue": formation_resolue or conv.derniere_formation_code,
            "suggestions": suggestions,
            "duree_ms": round(duree_ms, 1),
            "trace": {
                "cache_reponse": reponse_depuis_cache,
                "cache_embedding": bool(cache_utilise),
                "voyage_appele": not bool(cache_utilise) and not reponse_depuis_cache,
            },
        }

    # ========================================================
    # HANDLERS — sans Voyage, sans LLM
    # ========================================================

    def _entrees_indexees(self, allowed_formation_codes: set[str] | None = None, allowed_session_ids: set[str] | None = None, session_id: str | None = None):
        entrees = list(registre.charger_registre().values())
        return [
            e for e in entrees
            if e.statut == "indexe" and e.collection == "support" and e.formation_code
            and (allowed_formation_codes is None or e.formation_code in allowed_formation_codes)
            and (allowed_session_ids is None or str(e.session_id or "") in allowed_session_ids)
            and (session_id is None or str(e.session_id or "") == str(session_id))
        ]

    async def _repondre_catalogue(self, allowed_formation_codes: set[str] | None = None, allowed_session_ids: set[str] | None = None, session_id: str | None = None):
        indexees = self._entrees_indexees(allowed_formation_codes, allowed_session_ids, session_id)
        codes = sorted({e.formation_code for e in indexees if e.formation_code})
        if not codes:
            return "Aucune formation ne dispose actuellement d’un support indexé et exploitable.", []
        catalogue_par_code = {f.code: f for f in catalogue.charger_catalogue()}
        lignes = []
        for code in codes:
            formation = catalogue_par_code.get(code)
            titre = formation.titre if formation else code
            domaine = f" — domaine : {formation.domaine}" if formation and formation.domaine else ""
            nb = sum(1 for entree in indexees if entree.formation_code == code)
            lignes.append(f"- **{titre}** ({code}) — {nb} support(s) indexé(s){domaine}")
        return "Voici les formations pour lesquelles un support est effectivement indexé :\n\n" + "\n".join(lignes), []

    async def _repondre_inventaire(self, allowed_formation_codes: set[str] | None = None, allowed_session_ids: set[str] | None = None, session_id: str | None = None, hide_references: bool = False):
        indexees = self._entrees_indexees(allowed_formation_codes, allowed_session_ids, session_id)
        if not indexees:
            return "Aucun support de formation n’est actuellement indexé dans votre périmètre.", []
        par_formation: dict[str, list] = {}
        for entree in indexees:
            par_formation.setdefault(entree.formation_code or "", []).append(entree)
        titres = {f.code: f.titre for f in catalogue.charger_catalogue()}
        lignes = []
        for code, documents in sorted(par_formation.items()):
            chunks = sum(entree.nb_chunks or 0 for entree in documents)
            titre = titres.get(code, code)
            details = "" if hide_references else ": " + ", ".join(e.fichier for e in documents)
            lignes.append(f"- **{titre}** ({code}) : {len(documents)} support(s), {chunks} extrait(s) indexé(s){details}")
        total_chunks = sum(e.nb_chunks or 0 for e in indexees)
        return f"Inventaire des supports indexés : **{len(indexees)} support(s)** réparti(s) sur **{len(par_formation)} formation(s)**, soit **{total_chunks} extrait(s)**.\n\n" + "\n".join(lignes), []

    def _reponse_conversationnelle_locale(self, message: str = ""):
        msg = message.lower()
        # Questions d'identité → réponse spécifique FORMA-IA / ALTIORA
        if any(mot in msg for mot in ("créé", "cree", "crée", "créateur", "qui es-tu", "qui es tu",
                                      "qui t'a", "qui ta", "who are you", "c'est quoi", "c'est qui",
                                      "développé", "developpé", "développe", "construit", "fait par")):
            texte = (
                "Je suis **FORMA-IA**, l'assistant documentaire intelligent de la plateforme ALTIORA. "
                "Mon rôle est d'aider les directeurs, "
                "formateurs et assistants à accéder rapidement aux contenus de formation, "
                "aux supports indexés et aux informations de la plateforme. "
                "Comment puis-je vous aider aujourd'hui ?"
            )
        # Questions sur les capacités / ce que l'assistant peut faire
        elif any(mot in msg for mot in ("peux-tu", "peuxtu", "peux tu", "capable", "fonctionnalité",
                                        "fonctionnalite", "que sais-tu", "que fais-tu", "comment tu",
                                        "à quoi", "a quoi", "rôle", "role")):
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

    def _repondre_incomprehensible(self, message: str = "") -> str:
        """Réponse professionnelle lorsque le message n'est pas interprétable.
        Aucun appel Voyage ni LLM — pas de risque d'hallucination."""
        return (
            "Je n'ai pas bien compris votre message. "
            "Pourriez-vous reformuler votre question en quelques mots ?\n\n"
            "Par exemple :\n"
            "- « Quelles formations proposez-vous ? »\n"
            "- « Comment fonctionne le module TDR ? »\n"
            "- « Où est expliqué le deep learning ? »"
        )

    async def _repondre_conversationnel(self, message: str = "", conv: "memoire.Conversation | None" = None):
        # Si l'utilisateur a déjà échangé dans cette conversation,
        # ne pas répéter l'intro complète : réponse courte et contextualisée.
        deja_salue = conv and len(conv.echanges) >= 2
        if deja_salue:
            fallback = "Comment puis-je vous aider ?"
        else:
            fallback, _ = self._reponse_conversationnelle_locale(message)
        sources: list = []
        try:
            llm = get_llm_provider()
            historique_txt = _formater_historique(conv) if conv else ""
            contexte_hist = (
                f"\n\nHISTORIQUE (ne pas répéter, juste s'en souvenir) :\n{historique_txt}"
                if historique_txt else ""
            )
            reponse = await llm.generate_with_retry(
                system_prompt=(
                    "Tu es l'assistant conversationnel FORMA-IA d'ALTIORA PREST. "
                    "Réponds en français, avec un ton professionnel et cordial.\n"
                    "RÈGLES :\n"
                    "- Si l'utilisateur a DÉJÀ reçu la présentation de l'assistant, "
                    "réponds en UNE phrase courte et naturelle (pas l'intro complète).\n"
                    "- Si c'est le premier échange, présente-toi brièvement en 2 phrases max.\n"
                    "- Abréviations fréquentes : bjr=bonjour, slt/slut=salut, cc=coucou, "
                    "mrc=merci, bsr=bonsoir. Interprète-les naturellement.\n"
                    "- N'invente aucune donnée, résultat ou fonctionnalité.\n"
                    "- FORMA-IA accompagne : veille, TDR, offres, sessions, attestations, facturation, RAG.\n"
                    'Retourne UNIQUEMENT {"reponse":"..."}.'
                    + contexte_hist
                ),
                user_prompt=f"Message : {message}",
                temperature=0.25, max_tokens=200, json_mode=True, max_retries=1,
                reasoning_effort="low",
            )
            import json
            texte = json.loads(reponse["content"]).get("reponse")
            if isinstance(texte, str) and texte.strip():
                return texte.strip(), sources
        except Exception as exc:
            logger.debug("Réponse conversationnelle locale utilisée : %s", type(exc).__name__)
        return fallback, sources

    # ========================================================
    # HANDLERS — avec formation résolue (mémoire, sans Voyage, LLM oui)
    # ========================================================

    async def _repondre_contenu_formation(self, message, formation_code_force, session_id, module, conv, hide_references=False):
        if not session_id:
            return "Sélectionnez la session concernée pour afficher le contenu sans mélanger les supports d’autres sessions.", [], formation_code_force
        resolution = None
        if formation_code_force:
            resolution_formation = catalogue.obtenir_formation(formation_code_force)
            if resolution_formation:
                resolution = type("R", (), {"statut": "trouvee", "formation": resolution_formation})()
            else:
                # Les formations créées dans les sessions peuvent utiliser un
                # code propre au tenant, hors du catalogue RAG YAML global.
                cible = type("FormationCible", (), {"code": formation_code_force, "titre": formation_code_force})()
                resolution = type("R", (), {"statut": "trouvee", "formation": cible})()

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
        entrees = [e for e in registre.entrees_pour_session(session_id) if e.statut == "indexe" and e.formation_code == formation.code and (not module or e.module == module)]

        if not entrees:
            return f"Aucun support indexé pour la formation « {formation.titre} » pour l'instant.", [], formation.code

        contexte = "\n\n".join(
            (f"Résumé : {e.resume or 'non disponible'}\nPlan : {e.plan or 'non disponible'}"
             if hide_references else f"Support : {e.fichier}\nRésumé : {e.resume or 'non disponible'}\nPlan : {e.plan or 'non disponible'}")
            for e in entrees
        )
        resultat = await _appeler_llm_json(
            "reponse_contenu_formation.yaml", f"Formation : {formation.titre}\n\n{contexte}",
            consigne_additionnelle=("Ne cite aucun nom de fichier, page ou identifiant de document." if hide_references else None),
            historique=_formater_historique(conv),
        )

        if resultat and resultat.get("reponse"):
            texte = resultat["reponse"]
        else:
            texte = f"La formation **{formation.titre}** comprend {len(entrees)} support(s) indexé(s) :\n\n" + "\n".join(
                f"- {('Support : ' + e.fichier + ' — ') if not hide_references else ''}{e.resume or 'résumé non disponible'}" for e in entrees
            )

        sources = [] if hide_references else [{"fichier": e.fichier, "formation": formation.titre, "page": None, "score": None} for e in entrees]
        return texte, sources, formation.code

    # ========================================================
    # HANDLERS — avec Voyage (recherche vectorielle)
    # ========================================================

    async def _cache_utilise_pour(self, texte: str) -> bool:
        from app.services.rag.query_cache_service import depuis_cache
        provider = get_embedding_provider()
        return depuis_cache(texte, provider.modele_requete) is not None

    async def _repondre_synthese_thematique(self, message, conv=None, formation_code=None, session_id=None, module=None, allowed_session_ids=None, hide_references=False):
        cache_avant = await self._cache_utilise_pour(message)
        provider = get_embedding_provider()

        # Les synthèses multi-formations s'appuient sur les résumés dédiés.
        # Pour un module d'une session, chercher les chunks de cette session :
        # les résumés de session n'ont pas de module et ne doivent pas mélanger
        # les séances entre elles.
        collection = "support" if session_id and module else "resume_formation"
        resultats = await recherche.rechercher(
            message, collection=collection, top_k=8 if collection == "support" else 5,
            formation_code=formation_code,
            session_id=session_id,
            module=module,
            attente_max_s=ATTENTE_MAX_CHAT_S, repository=self.repository,
        )

        if not resultats:
            if formation_code:
                formation = catalogue.obtenir_formation(formation_code)
                titre = formation.titre if formation else formation_code
                return f"Aucun résumé indexé ne correspond à la formation « {titre} ». Indexez ses supports ou résumés pour obtenir une réponse ciblée.", [], provider.modele_requete, cache_avant
            return "Aucun résumé indexé ne permet une synthèse fiable sur ce sujet.", [], provider.modele_requete, cache_avant

        contexte = "\n\n".join(
            (f"Formation : {r.formation_titre or formation_code or 'Session sélectionnée'}\n"
             f"Module : {r.module or module or 'Général'}\nContenu : {r.contenu}")
            if collection == "support" else f"Formation : {r.formation_titre}\nRésumé : {r.contenu}"
            for r in resultats
        )
        resultat = await _appeler_llm_json(
            "reponse_synthese_thematique.yaml",
            f"THÈME DEMANDÉ : {message}\n\nCONTEXTE INDEXÉ :\n{contexte}",
            temperature=0.5,
            consigne_additionnelle=("Ne cite aucun nom de fichier, page ou identifiant de document." if hide_references else None),
            historique=_formater_historique(conv),
        )

        texte = resultat["reponse"] if resultat and resultat.get("reponse") else _reponse_mode_strict()
        sources = [{"fichier": None if collection == "resume_formation" else r.fichier, "formation": r.formation_titre, "page": None, "score": r.score} for r in resultats]
        return texte, ([] if hide_references else sources), provider.modele_requete, cache_avant

    async def _repondre_localisation(self, message, formation_code=None, session_id=None, module=None, hide_references=False):
        if not session_id:
            return "Sélectionnez la session concernée pour localiser le passage dans ses supports.", [], None, False
        cache_avant = await self._cache_utilise_pour(message)
        provider = get_embedding_provider()

        resultats = await recherche.rechercher(
            message, collection="support", top_k=8,
            formation_code=formation_code,
            session_id=session_id,
            module=module,
            attente_max_s=ATTENTE_MAX_CHAT_S, repository=self.repository,
        )

        if not resultats:
            if formation_code:
                formation = catalogue.obtenir_formation(formation_code)
                titre = formation.titre if formation else formation_code
                return f"Aucun support indexé ne correspond à la formation « {titre} ».", [], provider.modele_requete, cache_avant
            return _reponse_mode_strict(), [], provider.modele_requete, cache_avant

        # Groupé par fichier (mission §"localisation")
        par_fichier: dict[str, list] = {}
        for r in resultats:
            par_fichier.setdefault(r.fichier, []).append(r)

        lignes = []
        sources = []
        for fichier, occurrences in par_fichier.items():
            meilleur = max(occurrences, key=lambda r: r.score)
            pages = sorted({o.page_debut for o in occurrences if o.page_debut})
            plage = f"{min(pages)} à {max(pages)}" if len(pages) > 1 else (str(pages[0]) if pages else "?")
            if hide_references:
                lignes.append(f"- Extrait pertinent : « {meilleur.contenu[:250]}… »")
            else:
                lignes.append(f"- **{fichier}** — {meilleur.formation_titre or ''} — pages {plage} : « {meilleur.contenu[:150]}… »")
            sources.append({
                "fichier": fichier, "formation": meilleur.formation_titre,
                "page": meilleur.page_debut, "score": meilleur.score,
            })

        texte = ("Voici les passages pertinents dans les supports de votre formation :\n\n" if hide_references else "Voici où ce sujet est expliqué :\n\n") + "\n".join(lignes)
        return texte, ([] if hide_references else sources), provider.modele_requete, cache_avant

    async def _repondre_question_fond(self, message, conv=None, formation_code=None, session_id=None, module=None, hide_references=False):
        if not session_id:
            return "Je réponds uniquement à partir des supports indexés. Sélectionnez une session pour vérifier cette question sans mélanger les formations.", [], None, False
        cache_avant = await self._cache_utilise_pour(message)
        provider = get_embedding_provider()

        # Cache de réponse LLM
        cache_reponse = rcache.depuis_cache(message, "support", formation_code, session_id)
        if cache_reponse and hide_references != cache_reponse.get("hide_references"):
            cache_reponse = None
        if cache_reponse:
            return cache_reponse["texte"], cache_reponse["sources"], provider.modele_requete, True

        resultats = await recherche.rechercher(
            message, collection="support", top_k=8,
            formation_code=formation_code,
            session_id=session_id,
            module=module,
            attente_max_s=ATTENTE_MAX_CHAT_S, repository=self.repository,
        )

        if not resultats:
            if formation_code:
                formation = catalogue.obtenir_formation(formation_code)
                titre = formation.titre if formation else formation_code
                return f"Je n’ai trouvé aucun extrait indexé pour « {titre} ». Ajoutez des supports spécifiques à cette formation pour permettre une réponse fondée sur ses documents.", [], provider.modele_requete, cache_avant
            return "Aucun extrait indexé ne permet de répondre à cette question de façon fiable.", [], provider.modele_requete, cache_avant

        contexte = "\n\n".join(
            (r.contenu if hide_references else f"[{r.fichier}, p. {r.page_debut}]\n{r.contenu}")
            for r in resultats
        )
        if hide_references:
            contexte = f"{contexte}\n\nConsigne de confidentialité : ne cite pas de nom de document, de page ni de référence de source."
        resultat = await _appeler_llm_json(
            "reponse_question_fond.yaml",
            f"QUESTION : {message}\n\nEXTRAITS :\n{contexte}",
            temperature=0.5,
            consigne_additionnelle=("Ne cite aucun nom de fichier, page ou identifiant de document." if hide_references else None),
            historique=_formater_historique(conv),
        )

        texte = resultat["reponse"] if resultat and resultat.get("reponse") else _reponse_mode_strict()
        sources = [
            {"fichier": r.fichier, "formation": r.formation_titre, "page": r.page_debut, "score": r.score}
            for r in resultats
        ]
        rcache.mettre_en_cache(message, "support", {"texte": texte, "sources": sources, "hide_references": hide_references}, formation_code, session_id)
        return texte, sources, provider.modele_requete, cache_avant

    async def _repondre_aide_plateforme(self, message, hide_references=False, conv=None):
        cache_avant = await self._cache_utilise_pour(message)
        provider = get_embedding_provider()

        # Cache de réponse LLM (clé inclut la question uniquement — pas la conv)
        cache_reponse = rcache.depuis_cache(message, "aide_plateforme")
        if cache_reponse:
            return cache_reponse["texte"], cache_reponse["sources"], provider.modele_requete, True

        resultats = await recherche.rechercher(
            message, collection="aide_plateforme", top_k=5, seuil_min=0.20,
            attente_max_s=ATTENTE_MAX_CHAT_S, repository=self.repository,
        )

        historique = _formater_historique(conv)

        if not resultats:
            # Aucun document indexé : utiliser le guide statique + historique pour répondre
            # à des relances contextuelles ("explique l'étape 4" après avoir vu le guide).
            contexte_guide = GUIDE_DEMARRAGE_PLATEFORME
            resultat = await _appeler_llm_json(
                "reponse_aide_plateforme.yaml",
                f"QUESTION : {message}\n\nGUIDE FORMA-IA :\n{contexte_guide}",
                temperature=0.4,
                historique=historique,
            )
            if resultat and resultat.get("reponse"):
                texte = resultat["reponse"]
            else:
                texte = GUIDE_DEMARRAGE_PLATEFORME
            return texte, [], provider.modele_requete, cache_avant

        contexte = "\n\n".join(
            r.contenu if hide_references else f"[{r.fichier}]\n{r.contenu}"
            for r in resultats
        )
        resultat = await _appeler_llm_json(
            "reponse_aide_plateforme.yaml",
            f"QUESTION : {message}\n\nEXTRAITS DU GUIDE :\n{contexte}",
            temperature=0.4,
            historique=historique,
        )

        if resultat and resultat.get("reponse"):
            texte = resultat["reponse"]
        else:
            lignes = [
                (r.contenu[:250] if hide_references else f"**{r.fichier}** : {r.contenu[:200]}…")
                for r in resultats[:3]
            ]
            texte = "Voici ce que j'ai trouvé dans le guide :\n\n" + "\n\n".join(lignes)

        sources = [{"fichier": r.fichier, "formation": None, "page": r.page_debut, "score": r.score} for r in resultats]
        rcache.mettre_en_cache(message, "aide_plateforme", {"texte": texte, "sources": sources})
        return texte, ([] if hide_references else sources), provider.modele_requete, cache_avant

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
        "incomprehensible": [
            "Voir le catalogue des formations",
            "Poser une question sur la plateforme FORMA-IA",
        ],
    }

    @staticmethod
    def _suggestions(type_detecte: str) -> list[str]:
        return ChatOrchestrator._GABARITS_SUGGESTIONS.get(type_detecte, [])[:3]

    @staticmethod
    async def _suggestions_dynamiques(
        type_detecte: str, message: str, reponse: str
    ) -> list[str]:
        """Génère 2 suggestions de relance contextuelles via LLM.
        Retombe sur le gabarit statique si le LLM échoue ou est trop lent."""
        import asyncio
        import json as _json
        if type_detecte in ("hors_sujet", "inventaire", "catalogue", "conversationnel", "incomprehensible"):
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


_orchestrateur_instance: ChatOrchestrator | None = None


def get_chat_orchestrator() -> ChatOrchestrator:
    global _orchestrateur_instance
    if _orchestrateur_instance is None:
        _orchestrateur_instance = ChatOrchestrator()
    return _orchestrateur_instance
