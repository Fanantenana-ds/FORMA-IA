# app/orchestrator/rag_orchestrator.py
# ============================================================
# ORCHESTRATEUR — Ingestion RAG (module C3, Étape C)
# ============================================================
# Pipeline : fichier -> extraction -> nettoyage -> découpage -> embeddings
# -> base. Idempotent (SHA-256), reprise après interruption (par lot),
# ZIP sécurisé, résumés Groq (support puis formation).
# ============================================================

import logging
import os
import shutil
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.models.knowledge_base import KnowledgeBase
from app.services.rag.knowledge_repository import KnowledgeRepository
from app.services.rag.document_loader_service import (
    Segment, detect_file_type, extract_segments, pdf_necessite_ocr,
    compter_pages_pdf, FORMATS_INDEXABLES, FORMATS_IMAGE,
)
from app.services.rag.text_cleaner_service import clean_text
from app.services.rag.chunking_service import Chunk, chunk_segments, chunk_pptx_slides
from app.services.rag.embedding_provider import (
    get_embedding_provider, construire_lots, decouper_indices_par_lots, estimer_tokens,
)
from app.services.rag import registry_service as registre
from app.services.rag.catalogue_service import (
    obtenir_formation, formation_indexable, charger_catalogue,
)
from app.services.rag.resume_service import generer_resume_support, generer_resume_formation
from app.services.rag.zip_securite import verifier_et_lister, extraire_membre, ZipSecuriteError
from app.services.rag.recherche_service import (
    verifier_compatibilite_avec_base, IncompatibiliteModeleError,
)
from app.services.rag.llm_json_helper import appeler_llm_json
from app.services.rag import portfolio_service, syllabus_service, questions_service
from app.services.hitl import create_review
from app.services.backend_sync import review_sync

logger = logging.getLogger(__name__)

DOSSIER_FICHIERS_ORIGINAUX = Path(__file__).resolve().parents[2] / "data" / "rag" / "fichiers"

FORMATS_MEDIA_REFUSES = ("mp4", "avi", "mov", "mp3", "wav", "ogg", "mkv")

# Au-delà, on avertit dans le rapport (pas de blocage : l'orchestrateur ne
# peut pas "demander confirmation" en HTTP — cette confirmation interactive
# est du ressort de scripts/importer_corpus.py, Étape I).
DUREE_AVERTISSEMENT_MINUTES = 15


class RagOrchestrator:
    """Coordonne le pipeline d'ingestion RAG (C3)."""

    def __init__(self, repository: Optional[KnowledgeRepository] = None):
        self.embedding_provider = get_embedding_provider()
        self.repository = repository or KnowledgeRepository()

    # ========================================================
    # ESTIMATION — coût avant indexation
    # ========================================================

    def estimer_cout(self, textes: List[str]) -> Dict[str, Any]:
        """Tokens estimés, nombre de requêtes (lots), durée estimée à
        partir des limites RPM/TPM configurées."""
        tpm = self.embedding_provider.config.tpm
        rpm = self.embedding_provider.config.rpm
        lots = construire_lots(textes, tpm)
        tokens_total = sum(estimer_tokens(t) for t in textes)
        # Chaque lot consomme ~1 requête ; le débit est borné par rpm ET tpm.
        minutes_par_tpm = tokens_total / max(1, tpm)
        minutes_par_rpm = len(lots) / max(1, rpm)
        duree_min_estimee = max(minutes_par_tpm, minutes_par_rpm)

        return {
            "tokens_estimes": tokens_total,
            "nb_requetes": len(lots),
            "duree_estimee_min": round(duree_min_estimee, 1),
            "avertissement_duree": duree_min_estimee > DUREE_AVERTISSEMENT_MINUTES,
        }

    # ========================================================
    # INGESTION D'UN FICHIER
    # ========================================================

    async def ingerer_fichier(
        self,
        chemin_fichier: str,
        formation_code: Optional[str],
        collection: str = "support",
        nom_original: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Ingestion complète d'UN fichier déjà sur disque (pas une archive).
        Idempotent : si déjà indexé (même SHA-256), ne rappelle pas Voyage.
        """
        nom_original = nom_original or Path(chemin_fichier).name
        hash_fichier = registre.calculer_hash_fichier(chemin_fichier)

        if registre.deja_indexe(hash_fichier):
            logger.info(f"⏭️ Déjà indexé, ignoré : {nom_original}")
            return {"fichier": nom_original, "hash": hash_fichier, "statut": "deja_indexe"}

        entree = registre.initialiser_entree(hash_fichier, nom_original, formation_code, collection)

        # ── Compatibilité de famille de modèle (mission : une indexation avec
        # un modèle d'une autre famille que celle déjà en base est REFUSÉE) ──
        try:
            verifier_compatibilite_avec_base(
                self.embedding_provider.modele_document, collection, self.repository
            )
        except IncompatibiliteModeleError as exc:
            message = str(exc)
            registre.marquer_statut_special(
                hash_fichier, nom_original, formation_code, "erreur", message
            )
            return {"fichier": nom_original, "hash": hash_fichier, "statut": "erreur", "message": message}

        # ── Confidentialité (mission §"Confidentialité") ──
        if formation_code:
            formation = obtenir_formation(formation_code)
            if formation and not formation_indexable(formation):
                message = (
                    f"Formation '{formation_code}' marquée confidentielle : "
                    f"non indexée tant que VOYAGE_OPT_OUT n'est pas 'true' dans .env."
                )
                registre.marquer_statut_special(
                    hash_fichier, nom_original, formation_code, "erreur", message
                )
                logger.warning(f"🔒 {message}")
                return {"fichier": nom_original, "hash": hash_fichier, "statut": "erreur", "message": message}

        # ── Classification du type ──
        type_fichier = detect_file_type(chemin_fichier)

        if type_fichier in FORMATS_IMAGE:
            message = f"Image seule ('{type_fichier}') : non indexable en l'état (pas de texte)."
            registre.marquer_statut_special(
                hash_fichier, nom_original, formation_code, "non_indexable_image", message
            )
            return {"fichier": nom_original, "hash": hash_fichier, "statut": "non_indexable_image", "message": message}

        ext = Path(nom_original).suffix.lstrip(".").lower()
        if type_fichier not in FORMATS_INDEXABLES and type_fichier != "txt":
            if ext in FORMATS_MEDIA_REFUSES:
                message = f"Format non indexable (vidéo/audio) : '{ext}'."
            else:
                message = f"Format non reconnu ou non supporté : '{type_fichier or ext}'."
            registre.marquer_statut_special(
                hash_fichier, nom_original, formation_code, "erreur", message
            )
            return {"fichier": nom_original, "hash": hash_fichier, "statut": "erreur", "message": message}

        # ── Extraction ──
        try:
            segments = extract_segments(chemin_fichier, type_fichier)
        except Exception as exc:
            message = f"Erreur d'extraction : {type(exc).__name__} — {exc}"
            registre.marquer_statut_special(
                hash_fichier, nom_original, formation_code, "erreur", message
            )
            return {"fichier": nom_original, "hash": hash_fichier, "statut": "erreur", "message": message}

        if type_fichier == "pdf":
            nb_pages_total = compter_pages_pdf(chemin_fichier)
            if pdf_necessite_ocr(segments, nb_pages_total):
                message = (
                    f"PDF sans couche texte exploitable (< 50 caractères/page en "
                    f"moyenne sur {nb_pages_total} page(s)) : OCR nécessaire."
                )
                registre.marquer_statut_special(
                    hash_fichier, nom_original, formation_code, "ocr_necessaire", message
                )
                return {"fichier": nom_original, "hash": hash_fichier, "statut": "ocr_necessaire", "message": message}
            nb_pages = nb_pages_total
        else:
            nb_pages = len(segments)

        if not segments:
            message = "Aucun texte exploitable extrait de ce fichier."
            registre.marquer_statut_special(
                hash_fichier, nom_original, formation_code, "erreur", message
            )
            return {"fichier": nom_original, "hash": hash_fichier, "statut": "erreur", "message": message}

        # ── Nettoyage ──
        segments_propres = [Segment(numero=s.numero, texte=clean_text(s.texte)) for s in segments]

        # ── Découpage ──
        if type_fichier == "pptx":
            chunks = chunk_pptx_slides(segments_propres)
        else:
            chunks = chunk_segments(segments_propres)

        if not chunks:
            message = "Aucun chunk exploitable après nettoyage/découpage."
            registre.marquer_statut_special(
                hash_fichier, nom_original, formation_code, "erreur", message
            )
            return {"fichier": nom_original, "hash": hash_fichier, "statut": "erreur", "message": message}

        # ── Copie du fichier original (idempotence, référence future) ──
        DOSSIER_FICHIERS_ORIGINAUX.mkdir(parents=True, exist_ok=True)
        destination = DOSSIER_FICHIERS_ORIGINAUX / f"{hash_fichier}.{ext}"
        if not destination.exists():
            shutil.copyfile(chemin_fichier, destination)

        # ── Embeddings PAR LOT + insertion progressive (reprise après interruption) ──
        formation = obtenir_formation(formation_code) if formation_code else None
        titre = formation.titre if formation else None
        domaine = formation.domaine if formation else None
        annee = formation.annee_la_plus_recente() if formation else None

        textes_chunks = [c.texte for c in chunks]
        lots_indices = self._decouper_indices_par_lots(textes_chunks)

        lot_depart = entree.dernier_lot_termine + 1
        if lot_depart > 0:
            logger.info(f"🔁 Reprise après interruption : lot {lot_depart}/{len(lots_indices)}")

        try:
            for numero_lot in range(lot_depart, len(lots_indices)):
                indices = lots_indices[numero_lot]
                lot_chunks = [chunks[i] for i in indices]
                lot_textes = [c.texte for c in lot_chunks]

                vecteurs = await self.embedding_provider.embed_documents(lot_textes)

                lignes = [
                    KnowledgeBase(
                        collection=collection,
                        doc_hash=hash_fichier,
                        fichier=nom_original,
                        formation_code=formation_code,
                        formation_titre=titre,
                        domaine=domaine,
                        annee=annee,
                        type_support=type_fichier,
                        page_debut=chunk.page_debut,
                        page_fin=chunk.page_fin,
                        chunk_index=chunk.chunk_index,
                        contenu=chunk.texte,
                        embedding=vecteur,
                        modele_embed=self.embedding_provider.modele_document,
                    )
                    for chunk, vecteur in zip(lot_chunks, vecteurs)
                ]
                self.repository.inserer_chunks(lignes)

                registre.marquer_lot_termine(hash_fichier, numero_lot)
        except Exception as exc:
            message = f"Échec pendant l'indexation : {type(exc).__name__} — {exc}"
            registre.marquer_statut_special(
                hash_fichier, nom_original, formation_code, "erreur", message
            )
            return {"fichier": nom_original, "hash": hash_fichier, "statut": "erreur", "message": message}

        tokens_estimes = sum(estimer_tokens(t) for t in textes_chunks)
        registre.marquer_termine(
            hash_fichier, nb_pages=nb_pages, nb_chunks=len(chunks),
            tokens_estimes=tokens_estimes, modele_embed=self.embedding_provider.modele_document,
        )

        # ── Résumé par support (§9) — n'empêche jamais l'indexation d'avoir réussi ──
        resultat_resume = await generer_resume_support(segments_propres, nom_original)
        entree_a_jour = registre.obtenir_entree(hash_fichier)
        if resultat_resume and entree_a_jour:
            entree_a_jour.resume = resultat_resume.get("resume")
            entree_a_jour.plan = resultat_resume.get("plan", [])
            entree_a_jour.mots_cles = resultat_resume.get("mots_cles", [])
            entree_a_jour.resume_statut = "genere"
            registre.enregistrer_entree(entree_a_jour)
        elif entree_a_jour:
            entree_a_jour.resume_statut = "a_generer"
            registre.enregistrer_entree(entree_a_jour)

        # ── Résumé par formation (§10) ──
        if formation_code:
            await self.regenerer_resume_formation(formation_code)

        logger.info(f"✅ Indexé : {nom_original} ({len(chunks)} chunks, {nb_pages} page(s))")
        return {
            "fichier": nom_original, "hash": hash_fichier, "statut": "indexe",
            "nb_pages": nb_pages, "nb_chunks": len(chunks), "tokens_estimes": tokens_estimes,
            "resume_genere": bool(resultat_resume),
        }

    def _decouper_indices_par_lots(self, textes: List[str]) -> List[List[int]]:
        return decouper_indices_par_lots(textes, self.embedding_provider.config.tpm)

    # ========================================================
    # INDEXATION EN ARRIÈRE-PLAN (Étape H) — préparation synchrone,
    # rapide (hash + registre), le VRAI travail (Voyage, découpage,
    # insertion) est planifié par l'appelant via BackgroundTasks (FastAPI).
    # ========================================================

    def preparer_indexation(
        self, chemin_fichier: str, formation_code: Optional[str], collection: str = "support",
    ) -> Dict[str, Any]:
        """
        Calcule le hash (rapide, synchrone) et vérifie l'idempotence.
        Ne fait AUCUN appel Voyage. Retourne de quoi répondre
        immédiatement au client HTTP : {hash, fichier, deja_indexe}.
        """
        if not Path(chemin_fichier).exists():
            raise ValueError(f"Fichier introuvable : '{chemin_fichier}'.")

        nom_original = Path(chemin_fichier).name
        hash_fichier = registre.calculer_hash_fichier(chemin_fichier)

        if registre.deja_indexe(hash_fichier):
            return {"hash": hash_fichier, "fichier": nom_original, "deja_indexe": True}

        entree = registre.initialiser_entree(hash_fichier, nom_original, formation_code, collection)
        entree.statut = "en_cours"
        registre.enregistrer_entree(entree)
        return {"hash": hash_fichier, "fichier": nom_original, "deja_indexe": False}

    # ========================================================
    # SUPPRESSION D'UN DOCUMENT
    # ========================================================

    async def supprimer_document(self, hash_fichier: str) -> Dict[str, Any]:
        """Supprime les chunks d'un document de knowledge_base, retire son
        entrée du registre, met à jour le résumé de sa formation."""
        entree = registre.obtenir_entree(hash_fichier)
        if entree is None:
            return {"hash": hash_fichier, "statut": "introuvable"}

        nb_supprimes = self.repository.supprimer_par_hash(hash_fichier)

        formation_code = entree.formation_code
        registre.supprimer_entree(hash_fichier)

        fichier_copie = DOSSIER_FICHIERS_ORIGINAUX / f"{hash_fichier}.{Path(entree.fichier).suffix.lstrip('.')}"
        if fichier_copie.exists():
            fichier_copie.unlink()

        if formation_code:
            await self.regenerer_resume_formation(formation_code)

        logger.info(f"🗑️ Document supprimé : {entree.fichier} ({nb_supprimes} chunk(s))")
        return {"hash": hash_fichier, "statut": "supprime", "nb_chunks_supprimes": nb_supprimes}

    # ========================================================
    # RÉSUMÉ PAR FORMATION (§10)
    # ========================================================

    async def regenerer_resume_formation(self, formation_code: str) -> Optional[str]:
        """Régénère le résumé thématique d'une formation à partir des
        résumés de TOUS ses supports indexés, et l'upsert dans
        knowledge_base (collection='resume_formation')."""
        entrees = registre.entrees_pour_formation(formation_code)
        resumes = [e.resume for e in entrees if e.statut == "indexe" and e.resume]

        formation = obtenir_formation(formation_code)
        titre = formation.titre if formation else formation_code

        if not resumes:
            logger.info(f"ℹ️ Aucun résumé de support disponible pour '{formation_code}', pas de résumé formation.")
            return None

        resume_texte = await generer_resume_formation(titre, resumes)
        if not resume_texte:
            logger.warning(f"⚠️ Résumé de formation échoué pour '{formation_code}'.")
            return None

        vecteur = (await self.embedding_provider.embed_documents([resume_texte]))[0]

        ligne = KnowledgeBase(
            collection="resume_formation",
            fichier=None,
            formation_code=formation_code,
            formation_titre=titre,
            domaine=formation.domaine if formation else None,
            annee=formation.annee_la_plus_recente() if formation else None,
            contenu=resume_texte,
            embedding=vecteur,
            modele_embed=self.embedding_provider.modele_document,
        )
        self.repository.remplacer_resume_formation(formation_code, ligne)

        logger.info(f"📝 Résumé de formation mis à jour : {formation_code}")
        return resume_texte

    # ========================================================
    # INGESTION D'UN ZIP
    # ========================================================

    async def ingerer_zip(
        self, chemin_zip: str, formation_code: Optional[str], collection: str = "support",
        dossier_temporaire: Optional[Path] = None,
    ) -> Dict[str, Any]:
        """Vérifie la sécurité du ZIP, extrait chaque membre, ingère
        chacun individuellement. Un fichier en échec n'arrête pas les
        autres — rapport détaillé par fichier."""
        try:
            membres = verifier_et_lister(chemin_zip)
        except ZipSecuriteError as exc:
            return {"statut": "refuse", "message": str(exc), "fichiers": []}

        dossier_temporaire = dossier_temporaire or (
            Path(chemin_zip).parent / f"_extraction_{Path(chemin_zip).stem}"
        )

        rapport = []
        try:
            for membre in membres:
                nom = Path(membre.nom).name  # ignore la structure de dossiers du ZIP
                try:
                    chemin_extrait = extraire_membre(chemin_zip, membre.nom, dossier_temporaire)
                except ZipSecuriteError as exc:
                    rapport.append({"fichier": membre.nom, "statut": "refuse", "message": str(exc)})
                    continue

                resultat = await self.ingerer_fichier(
                    str(chemin_extrait), formation_code, collection, nom_original=nom,
                )
                rapport.append(resultat)
        finally:
            if dossier_temporaire.exists():
                shutil.rmtree(dossier_temporaire, ignore_errors=True)

        return {
            "statut": "termine",
            "nb_fichiers": len(rapport),
            "nb_indexes": sum(1 for r in rapport if r.get("statut") == "indexe"),
            "nb_deja_indexes": sum(1 for r in rapport if r.get("statut") == "deja_indexe"),
            "nb_erreurs": sum(1 for r in rapport if r.get("statut") in ("erreur", "refuse")),
            "fichiers": rapport,
        }

    # ========================================================
    # PORTFOLIO (Étape G)
    # ========================================================

    async def generer_portfolio(
        self, domaine: Optional[str] = None, reference_ao: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Génère le portfolio : totaux Python (catalogue), descriptions RAG
        par référence (LLM, MODE STRICT), review HITL (agent_rag_portfolio).
        Filtre optionnel par domaine.
        """
        formations = charger_catalogue()
        if domaine:
            formations = [f for f in formations if f.domaine == domaine]

        synthese = portfolio_service.calculer_synthese_chiffree(formations)
        tableau = portfolio_service.tableau_recapitulatif(formations)

        fiches = []
        sources_par_fiche = {}
        for formation in formations:
            for realisation in formation.realisations:
                fiche = await portfolio_service.generer_fiche_reference(
                    formation, realisation, appeler_llm_json, repository=self.repository,
                )
                fiches.append(fiche)
                if fiche.get("contenus_cles"):
                    sources_par_fiche[fiche["intitule"]] = [
                        f"chunk(s) indexé(s) de la formation {formation.code}"
                    ]

        resultat = {
            "success": True,
            "domaine": domaine,
            "reference_ao": reference_ao,
            "presentation_altiora": portfolio_service.lire_presentation_altiora(),
            "synthese_chiffree": synthese,
            "tableau_recapitulatif": tableau,
            "fiches_reference": fiches,
            "sources_par_fiche": sources_par_fiche,
            "metadata": {"generated_at": datetime.now().isoformat()},
        }

        review_id = create_review(
            agent_id="agent_rag_portfolio",
            data=resultat,
            summary=f"Portfolio — {domaine or 'toutes formations'} — {len(fiches)} référence(s)",
            criticity="critical",
        )
        resultat["_review_id"] = review_id
        resultat["_review_status"] = "pending_review"
        return resultat

    async def exporter_portfolio(self, review_id: str) -> Dict[str, Any]:
        """Export DOCX — UNIQUEMENT si le review est approuvé."""
        review = review_sync.load_approved_review(review_id, agent_ids=("agent_rag_portfolio",))
        donnees = review.get("data") or {}

        from app.services.rag.rag_document_generator import generer_docx_portfolio
        nom_fichier = f"portfolio_{review_id}.docx"
        chemin = generer_docx_portfolio(donnees, nom_fichier)
        return {"success": True, "docx_path": str(chemin)}

    # ========================================================
    # SYLLABUS (Étape G)
    # ========================================================

    async def generer_syllabus(
        self,
        formation_code: str,
        modules: List[Dict[str, Any]],
        options: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Génère le syllabus : somme des durées vérifiée en Python, contenu
        pédagogique rédigé par le LLM à partir des chunks RAG (MODE
        STRICT), review HITL (agent_rag_syllabus).
        """
        options = options or {}
        formation = obtenir_formation(formation_code)
        if not formation:
            raise ValueError(f"Formation '{formation_code}' introuvable au catalogue.")

        conforme, message_durees = syllabus_service.verifier_somme_durees(
            modules, formation.duree_jours or 0,
        )

        contenu = await syllabus_service.generer_contenu_pedagogique(
            formation.titre, modules, appeler_llm_json,
            formation_code=formation_code, repository=self.repository,
        )

        resultat = {
            "success": True,
            "intitule": formation.titre,
            "code": formation.code,
            "domaine": formation.domaine,
            "niveau": formation.niveau,
            "duree_jours": formation.duree_jours,
            "duree_heures": (formation.duree_jours or 0) * syllabus_service.HEURES_PAR_JOUR,
            "format": options.get("format", "[À compléter]"),
            "public_cible": options.get("public_cible", "[À compléter]"),
            "prerequis": options.get("prerequis", "[À compléter]"),
            "effectif_recommande": options.get("effectif_recommande", "[À compléter]"),
            "langue": options.get("langue", "Français"),
            "lieu": options.get("lieu", "[À compléter]"),
            "prepare_pour": options.get("prepare_pour", "[À compléter]"),
            "modules": modules,
            "verification_durees_conforme": conforme,
            "verification_durees_message": message_durees,
            **contenu,
            "sources_par_section": {"Programme": [f"formation {formation_code}"]} if modules else {},
            "metadata": {"generated_at": datetime.now().isoformat()},
        }

        review_id = create_review(
            agent_id="agent_rag_syllabus",
            data=resultat,
            summary=f"Syllabus — {formation.titre} — {message_durees}",
            criticity="critical",
        )
        resultat["_review_id"] = review_id
        resultat["_review_status"] = "pending_review"
        return resultat

    async def exporter_syllabus(self, review_id: str) -> Dict[str, Any]:
        """Export DOCX — UNIQUEMENT si le review est approuvé."""
        review = review_sync.load_approved_review(review_id, agent_ids=("agent_rag_syllabus",))
        donnees = review.get("data") or {}

        from app.services.rag.rag_document_generator import generer_docx_syllabus
        nom_fichier = f"syllabus_{review_id}.docx"
        chemin = generer_docx_syllabus(donnees, nom_fichier)
        return {"success": True, "docx_path": str(chemin)}

    # ========================================================
    # QUESTIONS (Étape G) — usage interne, PAS de HITL
    # ========================================================

    async def generer_questions(self, formation_code: str, nb_questions_max: int = 10) -> Dict[str, Any]:
        formation = obtenir_formation(formation_code)
        if not formation:
            raise ValueError(f"Formation '{formation_code}' introuvable au catalogue.")

        resultat = await questions_service.generer_questions(
            formation_code, formation.titre, appeler_llm_json,
            nb_questions_max=nb_questions_max, repository=self.repository,
        )
        return {"success": True, "formation_code": formation_code, **resultat}


_orchestrateur_instance: Optional[RagOrchestrator] = None


def get_rag_orchestrator() -> RagOrchestrator:
    global _orchestrateur_instance
    if _orchestrateur_instance is None:
        _orchestrateur_instance = RagOrchestrator()
    return _orchestrateur_instance
