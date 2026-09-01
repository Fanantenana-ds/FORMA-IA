# app/orchestrator/veille_orchestrator.py
# ============================================================
# FORMA-IA — M1 VEILLE MARCHÉ — ORCHESTRATEUR
# ============================================================
# Version : V8.0 — ajout du support texte collé / PDF
#
# Ce fichier NE CONTIENT PLUS de logique métier. Il coordonne :
#   TavilyService        -> recherche web (mode URL/query)
#   prefilter_service     -> filtrage déterministe (mode URL/query)
#   LLMAnalysisService     -> analyse Groq (compréhension) — COMMUN
#   ValidationService      -> qualité, normalisation, dédup — COMMUN
#   ClassificationService  -> domaine (Python, déterministe) — COMMUN
#   ScoringService          -> score final (Python, déterministe) — COMMUN
#   opportunity_sync        -> sync backend optionnelle, non bloquante
#
# 3 points d'entrée, 1 seul pipeline de post-traitement partagé
# (_finalize_opportunities), pour ne jamais dupliquer la logique
# de classification/scoring/validation :
#
#   analyser_opportunites(query)      -> Tavily + préfiltrage + Groq
#   analyser_texte(texte, source)     -> Groq directement sur le texte
#                                         (utilisé aussi par la route PDF,
#                                          après extraction du texte)
#
# Aucun import SQLAlchemy ici (cf. répartition des rôles :
# la persistance est la responsabilité du module Backend).
# ============================================================

import logging
import os
import time
from typing import Any, Dict, List, Optional

from app.services.veille.tavily_service import TavilyService
from app.services.veille.prefilter_service import rank_results
from app.services.veille.llm_analysis_service import (
    LLMAnalysisService,
    MAX_SOURCE_CHARS_EACH,
    MAX_SOURCE_CHARS_TOTAL,
)
from app.services.veille.classification_service import ClassificationService
from app.services.veille.scoring_service import ScoringService
from app.services.veille import validation_service
from app.services.backend_sync.opportunity_sync import sync_opportunities_to_backend

logger = logging.getLogger(__name__)

MIN_SCORE_VALIDATED = int(os.getenv("MIN_SCORE_VALIDATED", "60"))
MIN_SCORE_TO_REVIEW = int(os.getenv("MIN_SCORE_TO_REVIEW", "40"))

# IMPORTANT : la formule de confidence de classification_service.py
# (0.50 + 0.05 x nb_mots_clés, plafond 0.95) donne en pratique des
# valeurs entre 0.50 et 0.70 sur des résumés courts. Un seuil de
# 0.85 pour "validated" (suggestion générique non calibrée) viderait
# ce statut en permanence. 0.55 est calibré sur les vraies valeurs
# observées en test (0.55, 0.65) — à réajuster une fois le corpus de
# test annoté disponible, pas avant.
MIN_CONFIDENCE_VALIDATED = float(os.getenv("MIN_CONFIDENCE_VALIDATED", "0.55"))

MAX_RESULTS_AI = int(os.getenv("MAX_RESULTS_AI", "4"))

# Si le 1er lot de sources ne donne aucune opportunité, on retente
# avec le(s) lot(s) suivant(s) avant d'abandonner. 2 = jusqu'à
# 2 lots (8 sources sur 10 typiquement), borné pour ne pas exploser
# la latence totale (CDC <3s par appel, tolérable en cumulé sur 2).
MAX_FALLBACK_BATCHES = int(os.getenv("MAX_FALLBACK_BATCHES", "2"))


class VeilleOrchestrator:
    """Coordonne le pipeline M1 sans porter lui-même de logique métier."""

    def __init__(self):
        logger.info("🚀 Initialisation M1 Veille Orchestrator")

        self.tavily_service = TavilyService()
        self.llm_service = LLMAnalysisService()
        self.classification_service = ClassificationService()
        self.scoring_service = ScoringService()

    # ========================================================
    # ENTRÉE 1 — RECHERCHE WEB (Tavily + préfiltrage + Groq)
    # Comportement STRICTEMENT identique à la version en production.
    # ========================================================

    async def analyser_opportunites(self, query: str) -> Dict[str, Any]:

        query = str(query or "").strip()
        start_total = time.perf_counter()

        if not query:
            return self._empty_response(status="error", notes="Requête vide.")

        logger.info("=" * 60)
        logger.info("🚀 M1 VEILLE — DÉBUT")
        logger.info("🔍 Requête : %s", query)
        logger.info("=" * 60)

        # ----------------------------------------------------
        # 1 — TAVILY
        # ----------------------------------------------------

        raw_results = await self.tavily_service.search(query)

        if not raw_results:
            return self._empty_response(
                status="no_results",
                notes="Aucun résultat Tavily.",
                elapsed=time.perf_counter() - start_total,
            )

        # ----------------------------------------------------
        # 2 — CLASSEMENT COMPLET (pas de troncature ici)
        # ----------------------------------------------------

        ranked_results = rank_results(raw_results, query)

        if not ranked_results:
            return self._empty_response(
                status="no_results",
                notes="Aucun résultat après préfiltrage.",
                elapsed=time.perf_counter() - start_total,
                raw_count=len(raw_results),
            )

        # ----------------------------------------------------
        # 3/4 — ANALYSE LLM PAR LOTS, AVEC FALLBACK
        # ----------------------------------------------------
        # Si le lot 1 (top MAX_RESULTS_AI) ne donne aucune
        # opportunité, on essaie le lot suivant avant d'abandonner.
        # Évite de conclure "0 opportunité" sur la seule base d'un
        # sous-ensemble qui aurait pu mal tomber au préfiltrage.
        # ----------------------------------------------------

        groq_response = None
        groq_opportunities: List[Dict[str, Any]] = []
        filtered_results: List[Dict[str, Any]] = []
        last_notes = None
        any_groq_success = False
        batch_index = 0

        for batch_index in range(MAX_FALLBACK_BATCHES):
            start_idx = batch_index * MAX_RESULTS_AI
            end_idx = start_idx + MAX_RESULTS_AI
            batch = ranked_results[start_idx:end_idx]

            if not batch:
                break

            logger.info(
                "🔁 Lot %d/%d : %d source(s) analysée(s) par Groq",
                batch_index + 1,
                MAX_FALLBACK_BATCHES,
                len(batch),
            )

            batch_response = await self.llm_service.analyze(query, batch)
            filtered_results = batch  # dernier lot réellement tenté

            if batch_response is None:
                # Échec réseau/format sur ce lot : on tente quand
                # même le lot suivant plutôt que d'abandonner tout
                # de suite (peut être transitoire malgré les retries
                # internes déjà épuisés dans llm_analysis_service).
                logger.warning(
                    "⚠️ Lot %d : analyse Groq échouée, passage au lot suivant",
                    batch_index + 1,
                )
                continue

            any_groq_success = True
            groq_response = batch_response
            last_notes = batch_response.get("notes")
            batch_opportunities = batch_response.get("opportunities", [])

            if batch_opportunities:
                logger.info(
                    "✅ Lot %d : %d opportunité(s) trouvée(s) — arrêt du fallback",
                    batch_index + 1,
                    len(batch_opportunities),
                )
                groq_opportunities = batch_opportunities
                break

            logger.info(
                "ℹ️ Lot %d : aucune opportunité éligible", batch_index + 1
            )

        # ----------------------------------------------------
        # Aucun lot n'a pu être analysé (tous en échec réseau/format)
        # ----------------------------------------------------

        if not any_groq_success:
            result = validation_service.fallback_response(filtered_results)
            elapsed = time.perf_counter() - start_total
            result["statistics"]["processing_time_seconds"] = round(elapsed, 3)
            logger.info("🏁 M1 FALLBACK — FIN (%.3fs)", elapsed)
            return result

        # ----------------------------------------------------
        # Tous les lots tentés, mais 0 opportunité au final
        # ----------------------------------------------------

        if not groq_opportunities:
            elapsed = time.perf_counter() - start_total
            logger.info(
                "ℹ️ Aucune opportunité éligible après %d lot(s) testé(s)",
                min(MAX_FALLBACK_BATCHES, batch_index + 1),
            )
            return {
                "opportunities": [],
                "market_signals": (
                    groq_response.get("market_signals", []) if groq_response else []
                ),
                "total": 0,
                "status": "success",
                "ai_provider": "groq",
                "statistics": {
                    "raw_results": len(raw_results),
                    "filtered": len(ranked_results),
                    "batches_tried": min(MAX_FALLBACK_BATCHES, batch_index + 1),
                    "groq_results": 0,
                    "final": 0,
                    "madagascar": 0,
                    "processing_time_seconds": round(elapsed, 3),
                },
                "notes": last_notes or "Aucune opportunité éligible trouvée.",
            }

        # ----------------------------------------------------
        # 5→9 — post-traitement commun (classification, scoring,
        # dédup, validation schéma, sync backend, stats)
        # ----------------------------------------------------

        return await self._finalize_opportunities(
            groq_opportunities=groq_opportunities,
            groq_response=groq_response or {},
            start_total=start_total,
            extra_statistics={
                "raw_results": len(raw_results),
                "filtered": len(ranked_results),
                "sources_analyzed": len(filtered_results),
                "prefilter_candidates": len(ranked_results),
                "sources_sent_to_llm": len(filtered_results),
            },
        )

    # ========================================================
    # ENTRÉE 2 — TEXTE COLLÉ (pas de Tavily, pas de préfiltrage)
    # ========================================================
    # Utilisée directement par la route /analyser-texte, et par la
    # route /analyser-pdf une fois le texte extrait du PDF (PyPDF2,
    # déjà géré côté route). Le texte fourni EST la source à
    # analyser — aucune recherche web n'est effectuée.
    # ========================================================

    async def analyser_texte(
        self, texte: str, source: str = "manuel"
    ) -> Dict[str, Any]:

        texte = str(texte or "").strip()
        source_label = str(source or "manuel").strip() or "manuel"
        start_total = time.perf_counter()

        if not texte:
            return self._empty_response(status="error", notes="Texte vide.")

        logger.info("=" * 60)
        logger.info("🚀 M1 ANALYSE TEXTE DIRECT — DÉBUT (source: %s)", source_label)
        logger.info("📄 Longueur du texte : %d caractères", len(texte))
        logger.info("=" * 60)

        # Le prompt de llm_analysis_service tronque CHAQUE source à
        # MAX_SOURCE_CHARS_EACH (1000 car.) — on découpe donc le
        # texte en plusieurs "sources" pour exploiter tout le budget
        # disponible (MAX_SOURCE_CHARS_TOTAL, 4500 car.) au lieu de
        # perdre tout ce qui dépasse 1000 caractères.
        pseudo_sources = self._split_texte_en_sources(texte, source_label)

        # "query" ici ne représente pas une recherche web, mais
        # l'instruction d'analyse transmise au prompt veille.yaml
        # (placeholder {{QUERY}}).
        instruction = (
            f"Analyse directe d'un document fourni par l'utilisateur "
            f"(source : {source_label}). Pas de recherche web associée."
        )

        groq_response = await self.llm_service.analyze(
            query=instruction,
            results=pseudo_sources,
        )

        if groq_response is None:
            result = validation_service.fallback_response(pseudo_sources)
            elapsed = time.perf_counter() - start_total
            result["statistics"]["processing_time_seconds"] = round(elapsed, 3)
            logger.info("🏁 M1 ANALYSE TEXTE FALLBACK — FIN (%.3fs)", elapsed)
            return result

        groq_opportunities = groq_response.get("opportunities", [])

        return await self._finalize_opportunities(
            groq_opportunities=groq_opportunities,
            groq_response=groq_response,
            start_total=start_total,
            extra_statistics={
                "raw_results": 1,
                "filtered": 1,
                "sources_analyzed": len(pseudo_sources),
                "text_chunks": len(pseudo_sources),
                "text_length_chars": len(texte),
            },
        )

    @staticmethod
    def _split_texte_en_sources(
        texte: str, source_label: str
    ) -> List[Dict[str, Any]]:
        """
        Découpe un texte long en plusieurs blocs "source" compatibles
        avec llm_analysis_service._build_source_blocks(), pour ne pas
        perdre le contenu au-delà de MAX_SOURCE_CHARS_EACH.
        """
        chunks: List[Dict[str, Any]] = []
        total_chars = 0

        for start in range(0, len(texte), MAX_SOURCE_CHARS_EACH):
            chunk = texte[start:start + MAX_SOURCE_CHARS_EACH]
            if total_chars + len(chunk) > MAX_SOURCE_CHARS_TOTAL:
                break

            chunks.append({
                "title": f"{source_label} (partie {len(chunks) + 1})",
                "url": "",
                "content": chunk,
            })
            total_chars += len(chunk)

        if not chunks:
            # Filet de sécurité, ne devrait pas arriver (texte non vide
            # déjà vérifié par l'appelant).
            chunks.append({
                "title": source_label,
                "url": "",
                "content": texte[:MAX_SOURCE_CHARS_EACH],
            })

        if len(texte) > total_chars:
            logger.warning(
                "✂️ Texte tronqué pour l'analyse : %d/%d caractères envoyés à Groq",
                total_chars, len(texte),
            )

        return chunks

    # ========================================================
    # POST-TRAITEMENT COMMUN — ex-étapes 5→9, partagées par
    # analyser_opportunites ET analyser_texte
    # ========================================================

    async def _finalize_opportunities(
        self,
        groq_opportunities: List[Dict[str, Any]],
        groq_response: Dict[str, Any],
        start_total: float,
        extra_statistics: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:

        # ----------------------------------------------------
        # 5 — NORMALISATION / QUALITÉ / CLASSIFICATION / SCORING
        # ----------------------------------------------------

        normalized: List[Dict[str, Any]] = []

        for opportunity in groq_opportunities:

            cleaned = validation_service.normalize_opportunity(opportunity)
            if cleaned is None:
                continue

            if not validation_service.quality_filter(cleaned):
                continue

            cleaned.update(self.classification_service.classify(cleaned))
            cleaned["country_scope"] = self.classification_service.detect_country(
                cleaned
            )

            cleaned.update(self.scoring_service.score(cleaned))

            try:
                final_score = int(cleaned.get("score", 0))
            except (TypeError, ValueError):
                final_score = 0

            if final_score < MIN_SCORE_TO_REVIEW:
                continue

            try:
                final_confidence = float(cleaned.get("confidence", 0))
            except (TypeError, ValueError):
                final_confidence = 0.0

            # NOTE : conformément au dernier réglage validé (FANITSIA),
            # organizer_unclear reste dans les métadonnées (flags) à
            # titre informatif mais ne bloque plus le statut "validated".
            if (
                final_score >= MIN_SCORE_VALIDATED
                and final_confidence >= MIN_CONFIDENCE_VALIDATED
            ):
                cleaned["status"] = "validated"
            else:
                cleaned["status"] = "to_review"

            cleaned["ai_provider"] = "groq"
            cleaned["is_actionable"] = True

            normalized.append(cleaned)

        # ----------------------------------------------------
        # 6 — DÉDUPLICATION + TRI
        # ----------------------------------------------------

        normalized = validation_service.deduplicate(normalized)
        normalized.sort(key=lambda item: int(item.get("score", 0)), reverse=True)

        # ----------------------------------------------------
        # 7 — VALIDATION FINALE (schéma Pydantic partagé)
        # ----------------------------------------------------

        schema_valid: List[Dict[str, Any]] = []
        for opportunity in normalized:
            validated = validation_service.validate_against_schema(opportunity)
            if validated is not None:
                schema_valid.append(validated)

        # ----------------------------------------------------
        # 8 — SYNC BACKEND (optionnelle, non bloquante)
        # ----------------------------------------------------

        sync_result = await sync_opportunities_to_backend(schema_valid)

        # ----------------------------------------------------
        # 9 — STATISTIQUES + RÉPONSE
        # ----------------------------------------------------

        madagascar_count = sum(
            1 for o in schema_valid if o.get("country_scope") == "Madagascar"
        )

        elapsed = time.perf_counter() - start_total

        logger.info("🏁 M1 — FIN")
        logger.info("🤖 Résultats Groq : %d", len(groq_opportunities))
        logger.info("✅ Opportunités finales : %d", len(schema_valid))
        logger.info("🇲🇬 Madagascar : %d", madagascar_count)
        logger.info("⏱️ Temps total : %.3fs", elapsed)
        logger.info("=" * 60)

        statistics = {
            "groq_results": len(groq_opportunities),
            "final": len(schema_valid),
            "madagascar": madagascar_count,
            "backend_sync": sync_result,
            "processing_time_seconds": round(elapsed, 3),
            "llm_opportunities": len(groq_opportunities),
            "final_opportunities": len(schema_valid),
        }
        if extra_statistics:
            statistics.update(extra_statistics)

        return {
            "opportunities": schema_valid[:20],
            "market_signals": groq_response.get("market_signals", []),
            "total": len(schema_valid),
            "status": "success",
            "ai_provider": "groq",
            "statistics": statistics,
            "notes": groq_response.get(
                "notes", "Analyse M1 effectuée avec veille.yaml."
            ),
        }

    # ========================================================
    # HELPER — réponse vide standardisée
    # ========================================================

    @staticmethod
    def _empty_response(
        status: str,
        notes: str,
        elapsed: float = 0.0,
        raw_count: int = 0,
    ) -> Dict[str, Any]:
        return {
            "opportunities": [],
            "market_signals": [],
            "total": 0,
            "status": status,
            "ai_provider": None,
            "statistics": {
                "raw_results": raw_count,
                "filtered": 0,
                "groq_results": 0,
                "final": 0,
                "madagascar": 0,
                "processing_time_seconds": round(elapsed, 3),
            },
            "notes": notes,
        }

    # ========================================================
    # ALIAS
    # ========================================================

    async def rechercher(self, query: str) -> Dict[str, Any]:
        return await self.analyser_opportunites(query)