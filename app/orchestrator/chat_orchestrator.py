# app/orchestrator/chat_orchestrator.py
# ============================================================
# ORCHESTRATEUR — Assistant documentaire / chat (RAG, Étape E)
# ============================================================
# Route chaque message vers l'un des 9 types (voir type_detection_service),
# MODE STRICT partout (jamais de connaissances générales), jamais plus de
# 5 s d'attente Voyage pendant le chat, mémoire de conversation, journal.
# ============================================================

import logging
import re
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
ATTENTE_MAX_CHAT_S = 3.0
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


MAX_HISTORIQUE_ECHANGES = 20  # 10 tours utilisateur + 10 réponses assistant


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
        conversation_stockee = memoire.charger_conversation(conversation_id)
        # Une conversation peut servir à plusieurs sessions ; son historique
        # ne doit jamais faire fuiter le contenu d'une session vers une autre.
        conv = memoire.contexte_pour_session(conversation_stockee, session_id)

        message_original = message
        await progress("status", "Analyse de votre question…")
        type_detecte = await detecter_type(message, conv=conv, session_id=session_id)
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

        # Fix relance : "refaire"/"retry"/"encore" rejoue la dernière question réelle
        import unicodedata as _ud
        _msg_norm = "".join(
            c for c in _ud.normalize("NFKD", message.lower().strip())
            if not _ud.combining(c)
        )
        _MOTS_RELANCE = {
            "refaire", "refais", "retry", "reessai", "recommence", "recommencer",
            "encore", "suite", "continuer", "again", "refaire le resume",
            "refais le resume", "refaire la synthese", "refais la synthese",
        }
        est_relance = _msg_norm in _MOTS_RELANCE or bool(
            re.match(r"^(refais?|recommence|retry|again)\b", _msg_norm)
        )
        if est_relance and conv and conv.echanges:
            # Chercher le dernier message utilisateur non-relance
            for _e in reversed(conv.echanges):
                if _e.role == "utilisateur" and _e.texte != message_original:
                    _e_norm = "".join(
                        c for c in _ud.normalize("NFKD", _e.texte.lower().strip())
                        if not _ud.combining(c)
                    )
                    if _e_norm not in _MOTS_RELANCE and not re.match(
                        r"^(refais?|recommence|retry|again)\b", _e_norm
                    ):
                        message = _e.texte
                        type_detecte = await detecter_type(message, conv=conv, session_id=session_id)
                        break

        module_contexte = self._module_demande(message, session_id, module, conv)

        try:
            if type_detecte == "catalogue":
                texte, sources = await self._repondre_catalogue(allowed_formation_codes, allowed_session_ids, session_id)
            elif type_detecte == "inventaire":
                texte, sources = await self._repondre_inventaire(allowed_formation_codes, allowed_session_ids, session_id, hide_references)
            elif type_detecte == "contenu_formation":
                texte, sources, formation_resolue = await self._repondre_contenu_formation(message, formation_code, session_id, module_contexte, conv, hide_references)
            elif type_detecte == "synthese_thematique":
                # Le scope validé par la route s'applique aussi à la direction.
                # allowed_session_ids=None signifie « accès autorisé », pas
                # « ignorer la session sélectionnée ».
                texte, sources, modele_requete, cache_utilise = await self._repondre_synthese_thematique(
                    message, conv, formation_code, session_id, module_contexte,
                    allowed_session_ids, hide_references,
                )
            elif type_detecte == "localisation":
                # Les formateurs ne reçoivent pas les références de fichiers/pages.
                # Leur recherche reste strictement limitée à la session affectée.
                texte, sources, modele_requete, cache_utilise = await self._repondre_localisation(message, formation_code, session_id, module_contexte, hide_references, conv)
            elif type_detecte == "question_fond":
                texte, sources, modele_requete, cache_utilise = await self._repondre_question_fond(message, conv, formation_code, session_id, module_contexte, hide_references)
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
        except Exception as exc:
            logger.exception("❌ Chat : erreur inattendue (%s) : %s", type(exc).__name__, exc)
            texte = (
                "Une erreur est survenue pendant la préparation de la réponse. "
                "Veuillez reformuler votre question ou réessayer dans quelques instants."
            )
            sources = []
            statut = "erreur"

        await progress("status", "Structuration de la réponse…")

        if type_detecte not in ("hors_sujet", "incomprehensible") and sources and not hide_references:
            texte += MENTION_FIXE
        if hide_references:
            sources = []

        duree_ms = (time.perf_counter() - debut) * 1000

        if formation_code:
            formation_resolue = formation_code
        conversation_stockee = memoire.ajouter_echange(
            conversation_stockee, "utilisateur", message_original,
            session_id=session_id, module=module_contexte,
        )
        conversation_stockee = memoire.ajouter_echange(
            conversation_stockee, "assistant", texte,
            formation_code=formation_resolue, type_reponse=type_detecte,
            session_id=session_id, module=module_contexte,
        )
        if user_id:
            conversation_stockee.user_id = user_id
        memoire.sauvegarder_conversation(conversation_stockee)

        journal.enregistrer(
            question=message, type_detecte=type_detecte,
            formation_code=formation_resolue or conv.derniere_formation_code,
            nb_sources=len(sources), modele_requete=modele_requete,
            cache_utilise=bool(cache_utilise), duree_ms=duree_ms, statut=statut,
        )

        await progress("status", "Réponse préparée à partir des supports autorisés…")
        suggestions = self._suggestions(
            type_detecte, session_id=session_id, module=module_contexte, sources=sources,
        )

        return {
            "conversation_id": conversation_id,
            "type_reponse": type_detecte,
            "reponse": texte,
            "sources": sources,
            "formation_resolue": formation_resolue or conversation_stockee.derniere_formation_code,
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
            if e.statut == "indexe" and e.collection == "support"
            and (allowed_session_ids is None or str(e.session_id or "") in allowed_session_ids)
            and (session_id is None or str(e.session_id or "") == str(session_id))
        ]

    def _chunks_de_secours_session(self, session_id: str, module: str | None = None):
        """Read persisted chunks for the exact session/module without Voyage."""
        lister = getattr(self.repository, "lister_chunks_session", None)
        if not callable(lister):
            return []
        try:
            chunks = lister(
                session_id=session_id, collection="support", limit=200, module=module,
            )
        except Exception:
            logger.exception("Lecture directe des chunks de session impossible.")
            return []
        return [
            type("ChunkSession", (), {
                "contenu": str(chunk.get("contenu") or ""),
                "fichier": chunk.get("fichier"),
                "formation_titre": chunk.get("formation_titre"),
                "page_debut": chunk.get("page_debut"),
                "page_fin": chunk.get("page_fin"),
                "module": chunk.get("module"),
                "score": 0.0,
            })()
            for chunk in chunks
            if str(chunk.get("contenu") or "").strip()
        ]

    @staticmethod
    def _normaliser_module(texte: str) -> str:
        import unicodedata

        return " ".join("".join(
            c for c in unicodedata.normalize("NFKD", texte.casefold())
            if not unicodedata.combining(c)
        ).split())

    def _module_demande(
        self, message: str, session_id: str | None, module: str | None, conv=None,
    ) -> str | None:
        """Resolve a module named in the question to its exact indexed label."""
        if module:
            return module
        if not session_id:
            return None

        libelles = list(dict.fromkeys(
            entree.module.strip()
            for entree in registre.entrees_pour_session(session_id)
            if entree.module and entree.module.strip()
        ))
        import re
        def retrouver(texte: str) -> str | None:
            question = self._normaliser_module(texte)
            for libelle in sorted(libelles, key=len, reverse=True):
                normalise = self._normaliser_module(libelle)
                if normalise and normalise in question:
                    return libelle
            numero = re.search(r"\bmodule\s*([0-9]+)\b", question)
            if numero:
                prefixe = f"module {numero.group(1)}"
                return next((libelle for libelle in libelles
                             if self._normaliser_module(libelle).startswith(prefixe)), None)
            return None

        explicite = retrouver(message)
        if explicite:
            return explicite

        question = self._normaliser_module(message)
        if any(mot in question for mot in ("module suivant", "module d apres", "prochain module", "module apres")) and conv:
            precedent = None
            for echange in reversed(conv.echanges):
                precedent = echange.module or retrouver(echange.texte)
                if precedent in libelles:
                    break
            if precedent in libelles:
                position = libelles.index(precedent)
                if position + 1 < len(libelles):
                    return libelles[position + 1]
        return None

    @staticmethod
    def _requete_autonome(message: str, conv=None) -> str:
        """Add the prior user subject to short follow-ups before retrieval."""
        import unicodedata

        normalise = "".join(
            c for c in unicodedata.normalize("NFKD", message.casefold())
            if not unicodedata.combining(c)
        )
        tokens = normalise.split()
        relance = len(tokens) <= 5 or any(mot in normalise for mot in (
            "cela", "ce sujet", "cette notion", "ce contenu", "ce support",
            "plus de detail", "plus de precision", "la meme chose", "ce module",
        ))
        if not relance or not conv:
            return message
        precedent = next((
            echange.texte for echange in reversed(conv.echanges)
            if echange.role == "utilisateur" and echange.texte.strip()
            and echange.texte.strip() != message.strip()
        ), None)
        return f"{precedent} {message}" if precedent else message

    @staticmethod
    def _est_demande_exercices(message: str) -> bool:
        import unicodedata

        texte = "".join(
            c for c in unicodedata.normalize("NFKD", message.casefold())
            if not unicodedata.combining(c)
        )
        return any(mot in texte for mot in (
            "exercice", "quiz", "question orale", "questions a poser",
            "activite", "mise en situation", "test oral", "test de connaissance",
        ))

    def _chunks_exercices_session(self, session_id: str, module: str | None = None):
        """Fetch only existing session chunks that contain pedagogical activity evidence."""
        lister = getattr(self.repository, "lister_chunks_session", None)
        if not callable(lister):
            return []
        try:
            chunks = lister(session_id=session_id, collection="support", limit=200, module=module)
        except Exception:
            logger.exception("Lecture des supports de session pour les exercices impossible.")
            return []

        marqueurs = (
            "atelier", "exercice", "mise en situation", "cas pratique",
            "activite", "pratique", "appliquer", "tester", "quiz",
        )
        pertinents = [
            chunk for chunk in chunks
            if str(chunk.get("contenu") or "").strip()
            and any(marqueur in self._normaliser_module(str(chunk.get("contenu") or ""))
                    for marqueur in marqueurs)
        ]
        return [
            type("ChunkSession", (), {
                "contenu": str(chunk.get("contenu") or ""),
                "fichier": chunk.get("fichier"),
                "formation_titre": chunk.get("formation_titre"),
                "page_debut": chunk.get("page_debut"),
                "page_fin": chunk.get("page_fin"),
                "module": chunk.get("module"),
                "score": 0.0,
            })()
            for chunk in pertinents[:8]
        ]

    def _chunks_lexicaux_session(self, session_id: str, message: str, module: str | None = None):
        """Retrieve exact-session passages using lexical evidence before Voyage."""
        if module:
            return self._chunks_de_secours_session(session_id, module)
        lister = getattr(self.repository, "lister_chunks_session", None)
        if not callable(lister):
            return []
        try:
            chunks = lister(session_id=session_id, collection="support", limit=200, module=None)
        except Exception:
            logger.exception("Lecture des chunks pour le rappel lexical impossible.")
            return []

        import re
        import unicodedata

        normaliser = lambda texte: "".join(
            c for c in unicodedata.normalize("NFKD", texte.casefold())
            if not unicodedata.combining(c)
        )
        stop = {
            "alors", "avec", "dans", "depuis", "donne", "donner", "faire", "fait",
            "fais", "moi", "mon", "ma", "mes", "notre", "nos", "pour", "quoi",
            "quel", "quelle", "quels", "quelles", "qui", "comment", "est", "sont",
            "les", "des", "une", "un", "du", "de", "la", "le", "l", "et", "ou",
            "sur", "par", "ce", "ces", "cette", "cet", "support", "supports",
            "cours", "document", "documents", "formation", "formations", "module", "modules",
            "explique", "expliquer", "resume", "resumer", "clair", "claire", "tres",
        }
        termes = {
            terme for terme in re.findall(r"[a-z0-9]{3,}", normaliser(message))
            if terme not in stop
        }
        if not termes:
            return []

        notes = []
        for chunk in chunks:
            contenu = str(chunk.get("contenu") or "")
            texte = normaliser(contenu)
            presents = {terme for terme in termes if re.search(rf"\b{re.escape(terme)}\b", texte)}
            minimum = 1 if len(termes) <= 2 else 2
            if len(presents) >= minimum:
                notes.append((len(presents), chunk))
        notes.sort(key=lambda item: item[0], reverse=True)
        return [
            type("ChunkSession", (), {
                "contenu": str(chunk.get("contenu") or ""),
                "fichier": chunk.get("fichier"),
                "formation_titre": chunk.get("formation_titre"),
                "page_debut": chunk.get("page_debut"),
                "page_fin": chunk.get("page_fin"),
                "module": chunk.get("module"),
                "score": 0.0,
            })()
            for _score, chunk in notes[:8]
        ]

    def _chunks_session_par_requete(self, session_id: str, message: str, module: str | None = None):
        """Prefer exact module, activity evidence, then lexical matches before vector search."""
        if module:
            chunks = self._chunks_de_secours_session(session_id, module)
            if chunks:
                return chunks
        if self._est_demande_exercices(message):
            chunks = self._chunks_exercices_session(session_id, module)
            if chunks:
                return chunks
        return self._chunks_lexicaux_session(session_id, message, module)

    @staticmethod
    def _formater_chunk_source(chunk, hide_references: bool = False) -> str:
        if hide_references:
            return chunk.contenu
        fichier = chunk.fichier or "support"
        position = "diapo" if str(fichier).lower().endswith(".pptx") else "p."
        page = chunk.page_debut or "?"
        return f"[{fichier}, {position} {page}]\n{chunk.contenu}"

    async def _repondre_catalogue(self, allowed_formation_codes: set[str] | None = None, allowed_session_ids: set[str] | None = None, session_id: str | None = None):
        indexees = self._entrees_indexees(allowed_formation_codes, allowed_session_ids, session_id)
        codes = sorted({e.formation_code for e in indexees if e.formation_code})
        if not codes:
            if indexees:
                fichiers = sorted({e.fichier for e in indexees if e.fichier})
                return "Des supports sont indexés dans la session sélectionnée :\n\n" + "\n".join(f"- {fichier}" for fichier in fichiers), []
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
            if session_id:
                return "Aucun support indexé n’est rattaché à la session sélectionnée. Vérifiez le rattachement des documents à cette session.", []
            return "Aucun support de formation n’est actuellement indexé dans votre périmètre.", []
        par_formation: dict[str, list] = {}
        for entree in indexees:
            par_formation.setdefault(entree.formation_code or "Session sélectionnée", []).append(entree)
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
        # La session choisie dans l'interface est l'autorité métier. Elle peut
        # être hors catalogue YAML (ex. une session client FID) et ses supports
        # peuvent avoir un code vide ou différent du catalogue global.
        module = self._module_demande(message, session_id, module, conv)
        entrees = [
            e for e in registre.entrees_pour_session(session_id)
            if e.statut == "indexe" and e.collection == "support"
            and (not module or e.module == module)
        ]

        if not entrees:
            chunks_module = self._chunks_de_secours_session(session_id, module) if module else []
            if chunks_module:
                contexte_module = "\n\n".join(
                    self._formater_chunk_source(chunk, hide_references)
                    for chunk in chunks_module
                )
                resultat = await _appeler_llm_json(
                    "reponse_question_fond.yaml",
                    f"QUESTION : {message}\n\nEXTRAITS :\n{contexte_module}",
                    consigne_additionnelle=("Ne cite aucun nom de fichier, page ou identifiant de document." if hide_references else None),
                    historique=_formater_historique(conv),
                )
                texte = resultat.get("reponse") if resultat else None
                texte = texte or self._reponse_brute_depuis_chunks(chunks_module, hide_references)
                sources = [] if hide_references else [
                    {"fichier": chunk.fichier, "formation": chunk.formation_titre, "page": chunk.page_debut, "score": None}
                    for chunk in chunks_module
                ]
                return texte, sources, formation_code_force
            titre_absent = formation_code_force or "cette session"
            return f"Aucun support pédagogique indexé pour « {titre_absent} » pour l'instant.", [], formation_code_force

        formation = catalogue.obtenir_formation(formation_code_force) if formation_code_force else None
        titre_formation = (
            formation.titre if formation else
            formation_code_force or "la session sélectionnée"
        )
        code_formation = formation_code_force or next(
            (e.formation_code for e in entrees if e.formation_code), None
        )

        contexte = "\n\n".join(
            (f"Résumé : {e.resume or 'non disponible'}\nPlan : {e.plan or 'non disponible'}"
             if hide_references else f"Support : {e.fichier}\nRésumé : {e.resume or 'non disponible'}\nPlan : {e.plan or 'non disponible'}")
            for e in entrees
        )
        resultat = await _appeler_llm_json(
            "reponse_contenu_formation.yaml", f"Formation : {titre_formation}\n\n{contexte}",
            consigne_additionnelle=("Ne cite aucun nom de fichier, page ou identifiant de document." if hide_references else None),
            historique=_formater_historique(conv),
        )

        if resultat and resultat.get("reponse"):
            texte = resultat["reponse"]
        else:
            texte = f"La formation **{titre_formation}** comprend {len(entrees)} support(s) indexé(s) :\n\n" + "\n".join(
                f"- {('Support : ' + e.fichier + ' — ') if not hide_references else ''}{e.resume or 'résumé non disponible'}" for e in entrees
            )

        sources = [] if hide_references else [{"fichier": e.fichier, "formation": titre_formation, "page": None, "score": None} for e in entrees]
        return texte, sources, code_formation

    # ========================================================
    # HANDLERS — avec Voyage (recherche vectorielle)
    # ========================================================

    async def _cache_utilise_pour(self, texte: str) -> bool:
        from app.services.rag.query_cache_service import depuis_cache
        try:
            provider = get_embedding_provider()
            return depuis_cache(texte, provider.modele_requete) is not None
        except Exception:
            logger.debug("Cache d'embedding indisponible ; poursuite du chat sans cache.", exc_info=True)
            return False

    @staticmethod
    def _reponse_brute_depuis_chunks(chunks, hide_references: bool = False) -> str:
        if not chunks:
            return "Aucun extrait indexé ne permet de répondre à cette question de façon fiable."
        passages = []
        deja_vus = set()
        for chunk in chunks:
            contenu = " ".join(str(getattr(chunk, "contenu", "") or "").split())
            if not contenu or contenu.casefold() in deja_vus:
                continue
            deja_vus.add(contenu.casefold())
            extrait = contenu
            if len(extrait) > 480:
                extrait = extrait[:480].rsplit(" ", 1)[0].rstrip(" ,;:") + "…"
            source = ""
            if not hide_references:
                fichier = getattr(chunk, "fichier", None) or "support"
                position = "diapo" if str(fichier).lower().endswith(".pptx") else "p."
                page = getattr(chunk, "page_debut", None) or "?"
                source = f" [{fichier}, {position} {page}]"
            passages.append(f"- « {extrait} »{source}")
            if len(passages) == 4:
                break

        if not passages:
            return "Aucun extrait indexé ne permet de répondre à cette question de façon fiable."
        return (
            "Le modèle n’a pas pu produire une synthèse fiable. Pour rester fidèle aux documents, "
            "voici les passages indexés les plus pertinents :\n\n"
            + "\n\n".join(passages)
        )

    @staticmethod
    def _llm_refuse_contenu(texte: str) -> bool:
        normalise = ChatOrchestrator._normaliser_module(texte)
        marqueurs = (
            "aucun support", "aucun extrait", "ne traite pas ce sujet",
            "n'est pas aborde", "n’est pas aborde", "ne figure pas dans",
            "n'apparait pas dans", "n’apparaît pas dans", "pas mentionne dans",
        )
        return any(marqueur in normalise for marqueur in marqueurs)

    async def _repondre_synthese_thematique(self, message, conv=None, formation_code=None, session_id=None, module=None, allowed_session_ids=None, hide_references=False):
        cache_avant = await self._cache_utilise_pour(message)
        try:
            modele_requete = get_embedding_provider().modele_requete
        except Exception:
            modele_requete = None

        # Les synthèses multi-formations s'appuient sur les résumés dédiés.
        # Pour un module d'une session, chercher les chunks de cette session :
        # les résumés de session n'ont pas de module et ne doivent pas mélanger
        # les séances entre elles.
        # Une session choisie doit toujours interroger ses chunks de support,
        # même si aucun module précis n'est sélectionné. Les résumés globaux
        # peuvent être absents ou ne pas porter le même code client.
        collection = "support" if session_id else "resume_formation"
        module_cible = self._module_demande(message, session_id, module, conv)
        requete = self._requete_autonome(message, conv)
        resultats = self._chunks_session_par_requete(session_id, requete, module_cible) if session_id else []
        resultats_directs = bool(resultats)
        if not resultats:
            try:
                resultats = await recherche.rechercher(
                    requete, collection=collection, top_k=8 if collection == "support" else 5,
                    formation_code=formation_code,
                    session_id=session_id,
                    module=module_cible,
                    attente_max_s=ATTENTE_MAX_CHAT_S, repository=self.repository,
                )
                modele_requete = get_embedding_provider().modele_requete
            except Exception:
                logger.exception("Recherche thématique indisponible ; repli sur les chunks de la session.")

        if not resultats and session_id:
            resultats = self._chunks_de_secours_session(session_id, module_cible)
            resultats_directs = bool(resultats)

        if not resultats:
            if collection == "support":
                return "Aucun passage des supports de la session sélectionnée ne correspond à cette formulation. Reformulez la question ou choisissez un autre module.", [], modele_requete, cache_avant
            if formation_code:
                formation = catalogue.obtenir_formation(formation_code)
                titre = formation.titre if formation else formation_code
                return f"Aucun résumé indexé ne correspond à la formation « {titre} ». Indexez ses supports ou résumés pour obtenir une réponse ciblée.", [], modele_requete, cache_avant
            return "Aucun résumé indexé ne permet une synthèse fiable sur ce sujet.", [], modele_requete, cache_avant

        contexte = "\n\n".join(
            (
                f"Formation : {r.formation_titre or formation_code or 'Session sélectionnée'}\n"
                f"Module : {getattr(r, 'module', None) or module_cible or 'Général'}\n"
                f"{self._formater_chunk_source(r, hide_references)}"
            ) if collection == "support" else f"Formation : {r.formation_titre}\nRésumé : {r.contenu}"
            for r in resultats
        )
        prompt = "reponse_question_fond.yaml" if session_id else "reponse_synthese_thematique.yaml"
        resultat = await _appeler_llm_json(
            prompt,
            f"QUESTION : {message}\n\nEXTRAITS :\n{contexte}" if session_id else f"THÈME DEMANDÉ : {message}\n\nCONTEXTE INDEXÉ :\n{contexte}",
            temperature=0.5,
            consigne_additionnelle=("Ne cite aucun nom de fichier, page ou identifiant de document." if hide_references else None),
            historique=_formater_historique(conv),
        )

        texte = resultat["reponse"] if resultat and resultat.get("reponse") else self._reponse_brute_depuis_chunks(resultats, hide_references) if session_id else _reponse_mode_strict()
        if session_id and self._llm_refuse_contenu(texte):
            if resultats_directs:
                texte = self._reponse_brute_depuis_chunks(resultats, hide_references)
            else:
                sources = []
        else:
            sources = [{"fichier": None if collection == "resume_formation" else r.fichier, "formation": r.formation_titre, "page": None, "score": r.score} for r in resultats]
        return texte, ([] if hide_references else sources), modele_requete, cache_avant

    async def _repondre_localisation(self, message, formation_code=None, session_id=None, module=None, hide_references=False, conv=None):
        if not session_id:
            return "Sélectionnez la session concernée pour localiser le passage dans ses supports.", [], None, False
        cache_avant = await self._cache_utilise_pour(message)
        try:
            modele_requete = get_embedding_provider().modele_requete
        except Exception:
            modele_requete = None

        module_cible = self._module_demande(message, session_id, module, conv)
        requete = self._requete_autonome(message, conv)
        resultats = self._chunks_session_par_requete(session_id, requete, module_cible)
        if not resultats:
            try:
                resultats = await recherche.rechercher(
                    requete, collection="support", top_k=8,
                    formation_code=formation_code,
                    session_id=session_id,
                    module=module_cible,
                    attente_max_s=ATTENTE_MAX_CHAT_S, repository=self.repository,
                )
                modele_requete = get_embedding_provider().modele_requete
            except Exception:
                logger.exception("Recherche de localisation indisponible ; repli sur les chunks de la session.")

        # Une requête orale du type « prépare-moi des exercices à partir de ces
        # supports » peut être éloignée lexicalement des chunks. Si le ranking
        # ne renvoie rien, lire les chunks déjà vectorisés de la session exacte
        # (et du module choisi) sans nouvel embedding ni mélange de sessions.
        if not resultats and session_id:
            resultats = self._chunks_de_secours_session(session_id, module_cible)

        if not resultats:
            if formation_code:
                formation = catalogue.obtenir_formation(formation_code)
                titre = formation.titre if formation else formation_code
                return f"Aucun support indexé ne correspond à la formation « {titre} ».", [], modele_requete, cache_avant
            return _reponse_mode_strict(), [], modele_requete, cache_avant

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
        return texte, ([] if hide_references else sources), modele_requete, cache_avant

    async def _repondre_question_fond(self, message, conv=None, formation_code=None, session_id=None, module=None, hide_references=False):
        if not session_id:
            return "Je réponds uniquement à partir des supports indexés. Sélectionnez une session pour vérifier cette question sans mélanger les formations.", [], None, False
        cache_avant = await self._cache_utilise_pour(message)
        try:
            modele_requete = get_embedding_provider().modele_requete
        except Exception:
            modele_requete = None

        module_cible = self._module_demande(message, session_id, module, conv)
        requete = self._requete_autonome(message, conv)
        cache_namespace = f"support-v3:{module_cible or 'tous-modules'}"

        # L'ancien cache (sans portée de module) pouvait restituer un refus ou
        # une réponse d'un autre module. La version et le module font désormais
        # partie de l'espace de cache.
        cache_reponse = rcache.depuis_cache(requete, cache_namespace, formation_code, session_id)
        if cache_reponse and hide_references != cache_reponse.get("hide_references"):
            cache_reponse = None
        if cache_reponse:
            return cache_reponse["texte"], cache_reponse["sources"], modele_requete, True

        # Priorité au corpus exact de la session : module demandé, preuves
        # lexicales, puis recherche vectorielle si ces sources ne suffisent pas.
        resultats = self._chunks_session_par_requete(session_id, requete, module_cible)
        resultats_directs = bool(resultats)
        if not resultats:
            try:
                resultats = await recherche.rechercher(
                    requete, collection="support", top_k=8,
                    formation_code=formation_code,
                    session_id=session_id,
                    module=module_cible,
                    attente_max_s=ATTENTE_MAX_CHAT_S, repository=self.repository,
                )
                modele_requete = get_embedding_provider().modele_requete
            except Exception:
                logger.exception("Recherche vectorielle RAG indisponible ; repli sur les chunks de la session.")

        # Si Voyage échoue ou ne trouve rien, vérifier tout de même les chunks
        # déjà indexés de la session avant de conclure qu'aucun extrait n'existe.
        if not resultats:
            resultats = self._chunks_de_secours_session(session_id, module_cible)
            resultats_directs = bool(resultats)

        if not resultats:
            if formation_code:
                formation = catalogue.obtenir_formation(formation_code)
                titre = formation.titre if formation else formation_code
                return f"Je n’ai trouvé aucun extrait indexé pour « {titre} ». Ajoutez des supports spécifiques à cette formation pour permettre une réponse fondée sur ses documents.", [], modele_requete, cache_avant
            return "Aucun extrait indexé ne permet de répondre à cette question de façon fiable.", [], modele_requete, cache_avant

        contexte = "\n\n".join(
            self._formater_chunk_source(r, hide_references)
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

        texte = resultat["reponse"] if resultat and resultat.get("reponse") else self._reponse_brute_depuis_chunks(resultats, hide_references)
        sources = [
            {"fichier": r.fichier, "formation": r.formation_titre, "page": r.page_debut, "score": r.score}
            for r in resultats
        ]
        if self._llm_refuse_contenu(texte):
            if resultats_directs:
                texte = self._reponse_brute_depuis_chunks(resultats, hide_references)
            else:
                sources = []
        if resultat and resultat.get("reponse"):
            rcache.mettre_en_cache(requete, cache_namespace, {"texte": texte, "sources": sources, "hide_references": hide_references}, formation_code, session_id)
        return texte, sources, modele_requete, cache_avant

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
    def _suggestions(
        type_detecte: str,
        session_id: str | None = None,
        module: str | None = None,
        sources: list[dict[str, Any]] | None = None,
    ) -> list[str]:
        if session_id and type_detecte in {"contenu_formation", "synthese_thematique", "question_fond", "localisation"}:
            supports = [
                entry for entry in registre.entrees_pour_session(session_id)
                if entry.statut == "indexe" and entry.collection == "support"
            ]
            modules = list(dict.fromkeys(
                entry.module.strip() for entry in supports
                if entry.module and entry.module.strip()
            ))
            def ordre_module(name: str):
                match = re.search(r"\bmodule\s*(\d+)\b", ChatOrchestrator._normaliser_module(name))
                return (0, int(match.group(1))) if match else (1, name.casefold())

            modules.sort(key=ordre_module)
            module_courant = ChatOrchestrator._normaliser_module(module or "")
            position_courante = next(
                (index for index, name in enumerate(modules)
                 if ChatOrchestrator._normaliser_module(name) == module_courant),
                -1,
            )
            if position_courante >= 0 and position_courante + 1 < len(modules):
                prochain_module = modules[position_courante + 1]
                return [
                    f"Résume le module « {prochain_module} »",
                    f"Quels exercices sont prévus dans « {prochain_module} » ?",
                ]
            if position_courante < 0 and modules:
                premier_module = modules[0]
                return [
                    f"Résume le module « {premier_module} »",
                    f"Quels exercices sont prévus dans « {premier_module} » ?",
                ]
            if modules:
                return [
                    f"Quels exercices sont prévus dans « {modules[position_courante]} » ?",
                    f"Quelles notions clés contient « {modules[position_courante]} » ?",
                ]
            fichiers = list(dict.fromkeys(
                source.get("fichier") for source in (sources or [])
                if source.get("fichier")
            ))
            if fichiers:
                nom = fichiers[0]
                return [
                    f"Quels sont les points clés de « {nom} » ?",
                    f"Propose un exercice fondé sur « {nom} »",
                ]
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
