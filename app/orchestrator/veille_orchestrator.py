# app/orchestrator/veille_orchestrator.py
# ============================================================
# FORMA-IA — M1 VEILLE MARCHÉ — ORCHESTRATEUR
# ============================================================
# Version : V7.0 — architecture modulaire par services
#
# Ce fichier NE CONTIENT PLUS de logique métier. Il coordonne :
#   TavilyService        -> recherche web
#   prefilter_service     -> filtrage déterministe
#   LLMAnalysisService     -> analyse Groq (compréhension)
#   ValidationService      -> qualité, normalisation, dédup
#   ClassificationService  -> domaine (Python, déterministe)
#   ScoringService          -> score final (Python, déterministe)
#   opportunity_sync        -> sync backend optionnelle, non bloquante
#
# Aucun import SQLAlchemy ici (cf. répartition des rôles :
# la persistance est la responsabilité du module Backend).
# ============================================================

import logging
import os
import time
from typing import Any, Dict, List

from app.services.veille.tavily_service import TavilyService
from app.services.veille.prefilter_service import rank_results
from app.services.veille.llm_analysis_service import LLMAnalysisService
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
    # MÉTHODE PRINCIPALE
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

            organizer_is_unclear = "organizer_unclear" in (
                cleaned.get("flags") or []
            )

            # ============================================================
            # ✅ FANITSIA — IZAO FOTSINY NO OVANA
            # ============================================================
            # validated : score + confidence suffisants.
            # organizer_unclear ne bloque PLUS la validation ;
            # le flag reste dans les métadonnées pour information.
            if final_score >= MIN_SCORE_VALIDATED and final_confidence >= MIN_CONFIDENCE_VALIDATED:
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

        logger.info("🏁 M1 VEILLE — FIN")
        logger.info("🔎 Résultats Tavily : %d", len(raw_results))
        logger.info("🔧 Résultats classés : %d", len(ranked_results))
        logger.info("🤖 Résultats Groq : %d", len(groq_opportunities))
        logger.info("✅ Opportunités finales : %d", len(schema_valid))
        logger.info("🇲🇬 Madagascar : %d", madagascar_count)
        logger.info("⏱️ Temps total : %.3fs", elapsed)
        logger.info("=" * 60)

        return {
            "opportunities": schema_valid[:20],
            "market_signals": groq_response.get("market_signals", []),
            "total": len(schema_valid),
            "status": "success",
            "ai_provider": "groq",
            "statistics": {
                "raw_results": len(raw_results),
                "filtered": len(ranked_results),
                "sources_analyzed": len(filtered_results),
                "groq_results": len(groq_opportunities),
                "final": len(schema_valid),
                "madagascar": madagascar_count,
                "backend_sync": sync_result,
                "processing_time_seconds": round(elapsed, 3),
                # --- Noms explicites (CDC : clarté pour dashboard M8 /
                # jury) — mêmes valeurs, libellés sans ambiguïté ---
                "prefilter_candidates": len(ranked_results),
                "sources_sent_to_llm": len(filtered_results),
                "llm_opportunities": len(groq_opportunities),
                "final_opportunities": len(schema_valid),
            },
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









# # app/orchestrator/veille_orchestrator.py
# # ============================================================
# # FORMA-IA — M1 VEILLE MARCHÉ — ORCHESTRATEUR
# # ============================================================
# # Version : V7.0 — architecture modulaire par services
# #
# # Ce fichier NE CONTIENT PLUS de logique métier. Il coordonne :
# #   TavilyService        -> recherche web
# #   prefilter_service     -> filtrage déterministe
# #   LLMAnalysisService     -> analyse Groq (compréhension)
# #   ValidationService      -> qualité, normalisation, dédup
# #   ClassificationService  -> domaine (Python, déterministe)
# #   ScoringService          -> score final (Python, déterministe)
# #   opportunity_sync        -> sync backend optionnelle, non bloquante
# #
# # Aucun import SQLAlchemy ici (cf. répartition des rôles :
# # la persistance est la responsabilité du module Backend).
# # ============================================================

# import logging
# import os
# import time
# from typing import Any, Dict, List

# from app.services.veille.tavily_service import TavilyService
# from app.services.veille.prefilter_service import rank_results
# from app.services.veille.llm_analysis_service import LLMAnalysisService
# from app.services.veille.classification_service import ClassificationService
# from app.services.veille.scoring_service import ScoringService
# from app.services.veille import validation_service
# from app.services.backend_sync.opportunity_sync import sync_opportunities_to_backend

# logger = logging.getLogger(__name__)

# MIN_SCORE_VALIDATED = int(os.getenv("MIN_SCORE_VALIDATED", "60"))
# MIN_SCORE_TO_REVIEW = int(os.getenv("MIN_SCORE_TO_REVIEW", "40"))

# # IMPORTANT : la formule de confidence de classification_service.py
# # (0.50 + 0.05 x nb_mots_clés, plafond 0.95) donne en pratique des
# # valeurs entre 0.50 et 0.70 sur des résumés courts. Un seuil de
# # 0.85 pour "validated" (suggestion générique non calibrée) viderait
# # ce statut en permanence. 0.55 est calibré sur les vraies valeurs
# # observées en test (0.55, 0.65) — à réajuster une fois le corpus de
# # test annoté disponible, pas avant.
# MIN_CONFIDENCE_VALIDATED = float(os.getenv("MIN_CONFIDENCE_VALIDATED", "0.55"))

# MAX_RESULTS_AI = int(os.getenv("MAX_RESULTS_AI", "4"))

# # Si le 1er lot de sources ne donne aucune opportunité, on retente
# # avec le(s) lot(s) suivant(s) avant d'abandonner. 2 = jusqu'à
# # 2 lots (8 sources sur 10 typiquement), borné pour ne pas exploser
# # la latence totale (CDC <3s par appel, tolérable en cumulé sur 2).
# MAX_FALLBACK_BATCHES = int(os.getenv("MAX_FALLBACK_BATCHES", "2"))


# class VeilleOrchestrator:
#     """Coordonne le pipeline M1 sans porter lui-même de logique métier."""

#     def __init__(self):
#         logger.info("🚀 Initialisation M1 Veille Orchestrator")

#         self.tavily_service = TavilyService()
#         self.llm_service = LLMAnalysisService()
#         self.classification_service = ClassificationService()
#         self.scoring_service = ScoringService()

#     # ========================================================
#     # MÉTHODE PRINCIPALE
#     # ========================================================

#     async def analyser_opportunites(self, query: str) -> Dict[str, Any]:

#         query = str(query or "").strip()
#         start_total = time.perf_counter()

#         if not query:
#             return self._empty_response(status="error", notes="Requête vide.")

#         logger.info("=" * 60)
#         logger.info("🚀 M1 VEILLE — DÉBUT")
#         logger.info("🔍 Requête : %s", query)
#         logger.info("=" * 60)

#         # ----------------------------------------------------
#         # 1 — TAVILY
#         # ----------------------------------------------------

#         raw_results = await self.tavily_service.search(query)

#         if not raw_results:
#             return self._empty_response(
#                 status="no_results",
#                 notes="Aucun résultat Tavily.",
#                 elapsed=time.perf_counter() - start_total,
#             )

#         # ----------------------------------------------------
#         # 2 — CLASSEMENT COMPLET (pas de troncature ici)
#         # ----------------------------------------------------

#         ranked_results = rank_results(raw_results, query)

#         if not ranked_results:
#             return self._empty_response(
#                 status="no_results",
#                 notes="Aucun résultat après préfiltrage.",
#                 elapsed=time.perf_counter() - start_total,
#                 raw_count=len(raw_results),
#             )

#         # ----------------------------------------------------
#         # 3/4 — ANALYSE LLM PAR LOTS, AVEC FALLBACK
#         # ----------------------------------------------------
#         # Si le lot 1 (top MAX_RESULTS_AI) ne donne aucune
#         # opportunité, on essaie le lot suivant avant d'abandonner.
#         # Évite de conclure "0 opportunité" sur la seule base d'un
#         # sous-ensemble qui aurait pu mal tomber au préfiltrage.
#         # ----------------------------------------------------

#         groq_response = None
#         groq_opportunities: List[Dict[str, Any]] = []
#         filtered_results: List[Dict[str, Any]] = []
#         last_notes = None
#         any_groq_success = False

#         for batch_index in range(MAX_FALLBACK_BATCHES):
#             start_idx = batch_index * MAX_RESULTS_AI
#             end_idx = start_idx + MAX_RESULTS_AI
#             batch = ranked_results[start_idx:end_idx]

#             if not batch:
#                 break

#             logger.info(
#                 "🔁 Lot %d/%d : %d source(s) analysée(s) par Groq",
#                 batch_index + 1,
#                 MAX_FALLBACK_BATCHES,
#                 len(batch),
#             )

#             batch_response = await self.llm_service.analyze(query, batch)
#             filtered_results = batch  # dernier lot réellement tenté

#             if batch_response is None:
#                 # Échec réseau/format sur ce lot : on tente quand
#                 # même le lot suivant plutôt que d'abandonner tout
#                 # de suite (peut être transitoire malgré les retries
#                 # internes déjà épuisés dans llm_analysis_service).
#                 logger.warning(
#                     "⚠️ Lot %d : analyse Groq échouée, passage au lot suivant",
#                     batch_index + 1,
#                 )
#                 continue

#             any_groq_success = True
#             groq_response = batch_response
#             last_notes = batch_response.get("notes")
#             batch_opportunities = batch_response.get("opportunities", [])

#             if batch_opportunities:
#                 logger.info(
#                     "✅ Lot %d : %d opportunité(s) trouvée(s) — arrêt du fallback",
#                     batch_index + 1,
#                     len(batch_opportunities),
#                 )
#                 groq_opportunities = batch_opportunities
#                 break

#             logger.info(
#                 "ℹ️ Lot %d : aucune opportunité éligible", batch_index + 1
#             )

#         # ----------------------------------------------------
#         # Aucun lot n'a pu être analysé (tous en échec réseau/format)
#         # ----------------------------------------------------

#         if not any_groq_success:
#             result = validation_service.fallback_response(filtered_results)
#             elapsed = time.perf_counter() - start_total
#             result["statistics"]["processing_time_seconds"] = round(elapsed, 3)
#             logger.info("🏁 M1 FALLBACK — FIN (%.3fs)", elapsed)
#             return result

#         # ----------------------------------------------------
#         # Tous les lots tentés, mais 0 opportunité au final
#         # ----------------------------------------------------

#         if not groq_opportunities:
#             elapsed = time.perf_counter() - start_total
#             logger.info(
#                 "ℹ️ Aucune opportunité éligible après %d lot(s) testé(s)",
#                 min(MAX_FALLBACK_BATCHES, batch_index + 1),
#             )
#             return {
#                 "opportunities": [],
#                 "market_signals": (
#                     groq_response.get("market_signals", []) if groq_response else []
#                 ),
#                 "total": 0,
#                 "status": "success",
#                 "ai_provider": "groq",
#                 "statistics": {
#                     "raw_results": len(raw_results),
#                     "filtered": len(ranked_results),
#                     "batches_tried": min(MAX_FALLBACK_BATCHES, batch_index + 1),
#                     "groq_results": 0,
#                     "final": 0,
#                     "madagascar": 0,
#                     "processing_time_seconds": round(elapsed, 3),
#                 },
#                 "notes": last_notes or "Aucune opportunité éligible trouvée.",
#             }

#         # ----------------------------------------------------
#         # 5 — NORMALISATION / QUALITÉ / CLASSIFICATION / SCORING
#         # ----------------------------------------------------

#         normalized: List[Dict[str, Any]] = []

#         for opportunity in groq_opportunities:

#             cleaned = validation_service.normalize_opportunity(opportunity)
#             if cleaned is None:
#                 continue

#             if not validation_service.quality_filter(cleaned):
#                 continue

#             cleaned.update(self.classification_service.classify(cleaned))
#             cleaned["country_scope"] = self.classification_service.detect_country(
#                 cleaned
#             )

#             cleaned.update(self.scoring_service.score(cleaned))

#             try:
#                 final_score = int(cleaned.get("score", 0))
#             except (TypeError, ValueError):
#                 final_score = 0

#             if final_score < MIN_SCORE_TO_REVIEW:
#                 continue

#             try:
#                 final_confidence = float(cleaned.get("confidence", 0))
#             except (TypeError, ValueError):
#                 final_confidence = 0.0

#             organizer_is_unclear = "organizer_unclear" in (
#                 cleaned.get("flags") or []
#             )

#             # validated exige score ET confidence suffisants, ET une
#             # organisation clairement identifiée. Une organisation
#             # incertaine (organizer_unclear) force la revue humaine
#             # même si le score est bon — cohérent avec "mieux vaut
#             # une vraie opportunité que 10 faux positifs" (veille.yaml).
#             if (
#                 final_score >= MIN_SCORE_VALIDATED
#                 and final_confidence >= MIN_CONFIDENCE_VALIDATED
#                 and not organizer_is_unclear
#             ):
#                 cleaned["status"] = "validated"
#             else:
#                 cleaned["status"] = "to_review"

#             cleaned["ai_provider"] = "groq"
#             cleaned["is_actionable"] = True

#             normalized.append(cleaned)

#         # ----------------------------------------------------
#         # 6 — DÉDUPLICATION + TRI
#         # ----------------------------------------------------

#         normalized = validation_service.deduplicate(normalized)
#         normalized.sort(key=lambda item: int(item.get("score", 0)), reverse=True)

#         # ----------------------------------------------------
#         # 7 — VALIDATION FINALE (schéma Pydantic partagé)
#         # ----------------------------------------------------

#         schema_valid: List[Dict[str, Any]] = []
#         for opportunity in normalized:
#             validated = validation_service.validate_against_schema(opportunity)
#             if validated is not None:
#                 schema_valid.append(validated)

#         # ----------------------------------------------------
#         # 8 — SYNC BACKEND (optionnelle, non bloquante)
#         # ----------------------------------------------------

#         sync_result = await sync_opportunities_to_backend(schema_valid)

#         # ----------------------------------------------------
#         # 9 — STATISTIQUES + RÉPONSE
#         # ----------------------------------------------------

#         madagascar_count = sum(
#             1 for o in schema_valid if o.get("country_scope") == "Madagascar"
#         )

#         elapsed = time.perf_counter() - start_total

#         logger.info("🏁 M1 VEILLE — FIN")
#         logger.info("🔎 Résultats Tavily : %d", len(raw_results))
#         logger.info("🔧 Résultats classés : %d", len(ranked_results))
#         logger.info("🤖 Résultats Groq : %d", len(groq_opportunities))
#         logger.info("✅ Opportunités finales : %d", len(schema_valid))
#         logger.info("🇲🇬 Madagascar : %d", madagascar_count)
#         logger.info("⏱️ Temps total : %.3fs", elapsed)
#         logger.info("=" * 60)

#         return {
#             "opportunities": schema_valid[:20],
#             "market_signals": groq_response.get("market_signals", []),
#             "total": len(schema_valid),
#             "status": "success",
#             "ai_provider": "groq",
#             "statistics": {
#                 "raw_results": len(raw_results),
#                 "filtered": len(ranked_results),
#                 "sources_analyzed": len(filtered_results),
#                 "groq_results": len(groq_opportunities),
#                 "final": len(schema_valid),
#                 "madagascar": madagascar_count,
#                 "backend_sync": sync_result,
#                 "processing_time_seconds": round(elapsed, 3),
#                 # --- Noms explicites (CDC : clarté pour dashboard M8 /
#                 # jury) — mêmes valeurs, libellés sans ambiguïté ---
#                 "prefilter_candidates": len(ranked_results),
#                 "sources_sent_to_llm": len(filtered_results),
#                 "llm_opportunities": len(groq_opportunities),
#                 "final_opportunities": len(schema_valid),
#             },
#             "notes": groq_response.get(
#                 "notes", "Analyse M1 effectuée avec veille.yaml."
#             ),
#         }

#     # ========================================================
#     # HELPER — réponse vide standardisée
#     # ========================================================

#     @staticmethod
#     def _empty_response(
#         status: str,
#         notes: str,
#         elapsed: float = 0.0,
#         raw_count: int = 0,
#     ) -> Dict[str, Any]:
#         return {
#             "opportunities": [],
#             "market_signals": [],
#             "total": 0,
#             "status": status,
#             "ai_provider": None,
#             "statistics": {
#                 "raw_results": raw_count,
#                 "filtered": 0,
#                 "groq_results": 0,
#                 "final": 0,
#                 "madagascar": 0,
#                 "processing_time_seconds": round(elapsed, 3),
#             },
#             "notes": notes,
#         }

#     # ========================================================
#     # ALIAS
#     # ========================================================

#     async def rechercher(self, query: str) -> Dict[str, Any]:
#         return await self.analyser_opportunites(query)



# # app/orchestrator/veille_orchestrator.py
# # ============================================================
# # FORMA-IA — M1 VEILLE MARCHÉ — ORCHESTRATEUR
# # ============================================================
# # Version : V7.0 — architecture modulaire par services
# #
# # Ce fichier NE CONTIENT PLUS de logique métier. Il coordonne :
# #   TavilyService        -> recherche web
# #   prefilter_service     -> filtrage déterministe
# #   LLMAnalysisService     -> analyse Groq (compréhension)
# #   ValidationService      -> qualité, normalisation, dédup
# #   ClassificationService  -> domaine (Python, déterministe)
# #   ScoringService          -> score final (Python, déterministe)
# #   opportunity_sync        -> sync backend optionnelle, non bloquante
# #
# # Aucun import SQLAlchemy ici (cf. répartition des rôles :
# # la persistance est la responsabilité du module Backend).
# # ============================================================

# import logging
# import os
# import time
# from typing import Any, Dict, List, Optional

# from app.services.veille.tavily_service import TavilyService
# from app.services.veille.prefilter_service import rank_results
# from app.services.veille.llm_analysis_service import LLMAnalysisService
# from app.services.veille.classification_service import ClassificationService
# from app.services.veille.scoring_service import ScoringService
# from app.services.veille import validation_service
# from app.services.backend_sync.opportunity_sync import sync_opportunities_to_backend

# logger = logging.getLogger(__name__)

# MIN_SCORE_VALIDATED = int(os.getenv("MIN_SCORE_VALIDATED", "60"))
# MIN_SCORE_TO_REVIEW = int(os.getenv("MIN_SCORE_TO_REVIEW", "40"))

# # IMPORTANT : la formule de confidence de classification_service.py
# # (0.50 + 0.05 x nb_mots_clés, plafond 0.95) donne en pratique des
# # valeurs entre 0.50 et 0.70 sur des résumés courts. Un seuil de
# # 0.85 pour "validated" (suggestion générique non calibrée) viderait
# # ce statut en permanence. 0.55 est calibré sur les vraies valeurs
# # observées en test (0.55, 0.65) — à réajuster une fois le corpus de
# # test annoté disponible, pas avant.
# MIN_CONFIDENCE_VALIDATED = float(os.getenv("MIN_CONFIDENCE_VALIDATED", "0.55"))

# MAX_RESULTS_AI = int(os.getenv("MAX_RESULTS_AI", "4"))

# # Si le 1er lot de sources ne donne aucune opportunité, on retente
# # avec le(s) lot(s) suivant(s) avant d'abandonner. 2 = jusqu'à
# # 2 lots (8 sources sur 10 typiquement), borné pour ne pas exploser
# # la latence totale (CDC <3s par appel, tolérable en cumulé sur 2).
# MAX_FALLBACK_BATCHES = int(os.getenv("MAX_FALLBACK_BATCHES", "2"))


# class VeilleOrchestrator:
#     """Coordonne le pipeline M1 sans porter lui-même de logique métier."""

#     def __init__(self):
#         logger.info("🚀 Initialisation M1 Veille Orchestrator")

#         self.tavily_service = TavilyService()
#         self.llm_service = LLMAnalysisService()
#         self.classification_service = ClassificationService()
#         self.scoring_service = ScoringService()

#     # ========================================================
#     # POST-TRAITEMENT D'UNE OPPORTUNITÉ (partagé par toutes les
#     # routes M1 : rechercher, analyser-texte, analyser-pdf)
#     # ========================================================

#     def _process_single_opportunity(
#         self, opportunity: Dict[str, Any]
#     ) -> Optional[Dict[str, Any]]:
#         """
#         Normalise, filtre, classifie et note UNE opportunité brute
#         renvoyée par Groq. Retourne None si elle est rejetée à une
#         étape quelconque.
#         """

#         cleaned = validation_service.normalize_opportunity(opportunity)
#         if cleaned is None:
#             return None

#         if not validation_service.quality_filter(cleaned):
#             return None

#         cleaned.update(self.classification_service.classify(cleaned))
#         cleaned["country_scope"] = self.classification_service.detect_country(
#             cleaned
#         )

#         cleaned.update(self.scoring_service.score(cleaned))

#         try:
#             final_score = int(cleaned.get("score", 0))
#         except (TypeError, ValueError):
#             final_score = 0

#         if final_score < MIN_SCORE_TO_REVIEW:
#             return None

#         try:
#             final_confidence = float(cleaned.get("confidence", 0))
#         except (TypeError, ValueError):
#             final_confidence = 0.0

#         organizer_is_unclear = "organizer_unclear" in (cleaned.get("flags") or [])

#         if (
#             final_score >= MIN_SCORE_VALIDATED
#             and final_confidence >= MIN_CONFIDENCE_VALIDATED
#             and not organizer_is_unclear
#         ):
#             cleaned["status"] = "validated"
#         else:
#             cleaned["status"] = "to_review"

#         cleaned["ai_provider"] = "groq"
#         cleaned["is_actionable"] = True

#         return cleaned

#     # ========================================================
#     # ANALYSE DE TEXTE DIRECT — PAS DE TAVILY
#     # ========================================================
#     # Utilisée par /analyser-texte et /analyser-pdf (après
#     # extraction du texte du PDF). Le texte fourni EST la source
#     # à analyser — on ne fait AUCUNE recherche web dessus.
#     # ========================================================

#     async def analyser_texte(
#         self, texte: str, source: str = "manuel"
#     ) -> Dict[str, Any]:

#         texte = str(texte or "").strip()
#         start_total = time.perf_counter()

#         if not texte:
#             return self._empty_response(status="error", notes="Texte vide.")

#         logger.info("=" * 60)
#         logger.info("🚀 M1 ANALYSE TEXTE DIRECT — DÉBUT (source: %s)", source)
#         logger.info("📄 Longueur du texte : %d caractères", len(texte))
#         logger.info("=" * 60)

#         # Le texte EST la source unique — encapsulé au même format
#         # que les résultats Tavily pour réutiliser llm_analysis_service
#         # sans dupliquer sa logique de construction de prompt.
#         pseudo_source = {
#             "title": source or "Texte fourni directement",
#             "url": "",
#             "content": texte,
#         }

#         groq_response = await self.llm_service.analyze(
#             query="Analyse directe d'un texte fourni par l'utilisateur (pas de recherche web).",
#             results=[pseudo_source],
#         )

#         if groq_response is None:
#             result = validation_service.fallback_response([pseudo_source])
#             elapsed = time.perf_counter() - start_total
#             result["statistics"]["processing_time_seconds"] = round(elapsed, 3)
#             logger.info("🏁 M1 ANALYSE TEXTE FALLBACK — FIN (%.3fs)", elapsed)
#             return result

#         groq_opportunities = groq_response.get("opportunities", [])

#         normalized: List[Dict[str, Any]] = []
#         for opportunity in groq_opportunities:
#             processed = self._process_single_opportunity(opportunity)
#             if processed is not None:
#                 normalized.append(processed)

#         normalized = validation_service.deduplicate(normalized)
#         normalized.sort(key=lambda item: int(item.get("score", 0)), reverse=True)

#         schema_valid: List[Dict[str, Any]] = []
#         for opportunity in normalized:
#             validated = validation_service.validate_against_schema(opportunity)
#             if validated is not None:
#                 schema_valid.append(validated)

#         sync_result = await sync_opportunities_to_backend(schema_valid)

#         elapsed = time.perf_counter() - start_total

#         logger.info("🏁 M1 ANALYSE TEXTE — FIN")
#         logger.info("🤖 Résultats Groq : %d", len(groq_opportunities))
#         logger.info("✅ Opportunités finales : %d", len(schema_valid))
#         logger.info("⏱️ Temps total : %.3fs", elapsed)
#         logger.info("=" * 60)

#         return {
#             "opportunities": schema_valid,
#             "market_signals": groq_response.get("market_signals", []),
#             "total": len(schema_valid),
#             "status": "success",
#             "ai_provider": "groq",
#             "statistics": {
#                 "sources_analyzed": 1,
#                 "llm_opportunities": len(groq_opportunities),
#                 "final_opportunities": len(schema_valid),
#                 "backend_sync": sync_result,
#                 "processing_time_seconds": round(elapsed, 3),
#             },
#             "notes": groq_response.get("notes", ""),
#         }

#     # ========================================================
#     # MÉTHODE PRINCIPALE
#     # ========================================================

#     async def analyser_opportunites(self, query: str) -> Dict[str, Any]:

#         query = str(query or "").strip()
#         start_total = time.perf_counter()

#         if not query:
#             return self._empty_response(status="error", notes="Requête vide.")

#         logger.info("=" * 60)
#         logger.info("🚀 M1 VEILLE — DÉBUT")
#         logger.info("🔍 Requête : %s", query)
#         logger.info("=" * 60)

#         # ----------------------------------------------------
#         # 1 — TAVILY
#         # ----------------------------------------------------

#         raw_results = await self.tavily_service.search(query)

#         if not raw_results:
#             return self._empty_response(
#                 status="no_results",
#                 notes="Aucun résultat Tavily.",
#                 elapsed=time.perf_counter() - start_total,
#             )

#         # ----------------------------------------------------
#         # 2 — CLASSEMENT COMPLET (pas de troncature ici)
#         # ----------------------------------------------------

#         ranked_results = rank_results(raw_results, query)

#         if not ranked_results:
#             return self._empty_response(
#                 status="no_results",
#                 notes="Aucun résultat après préfiltrage.",
#                 elapsed=time.perf_counter() - start_total,
#                 raw_count=len(raw_results),
#             )

#         # ----------------------------------------------------
#         # 3/4 — ANALYSE LLM PAR LOTS, AVEC FALLBACK
#         # ----------------------------------------------------
#         # Si le lot 1 (top MAX_RESULTS_AI) ne donne aucune
#         # opportunité, on essaie le lot suivant avant d'abandonner.
#         # Évite de conclure "0 opportunité" sur la seule base d'un
#         # sous-ensemble qui aurait pu mal tomber au préfiltrage.
#         # ----------------------------------------------------

#         groq_response = None
#         groq_opportunities: List[Dict[str, Any]] = []
#         filtered_results: List[Dict[str, Any]] = []
#         last_notes = None
#         any_groq_success = False

#         for batch_index in range(MAX_FALLBACK_BATCHES):
#             start_idx = batch_index * MAX_RESULTS_AI
#             end_idx = start_idx + MAX_RESULTS_AI
#             batch = ranked_results[start_idx:end_idx]

#             if not batch:
#                 break

#             logger.info(
#                 "🔁 Lot %d/%d : %d source(s) analysée(s) par Groq",
#                 batch_index + 1,
#                 MAX_FALLBACK_BATCHES,
#                 len(batch),
#             )

#             batch_response = await self.llm_service.analyze(query, batch)
#             filtered_results = batch  # dernier lot réellement tenté

#             if batch_response is None:
#                 # Échec réseau/format sur ce lot : on tente quand
#                 # même le lot suivant plutôt que d'abandonner tout
#                 # de suite (peut être transitoire malgré les retries
#                 # internes déjà épuisés dans llm_analysis_service).
#                 logger.warning(
#                     "⚠️ Lot %d : analyse Groq échouée, passage au lot suivant",
#                     batch_index + 1,
#                 )
#                 continue

#             any_groq_success = True
#             groq_response = batch_response
#             last_notes = batch_response.get("notes")
#             batch_opportunities = batch_response.get("opportunities", [])

#             if batch_opportunities:
#                 logger.info(
#                     "✅ Lot %d : %d opportunité(s) trouvée(s) — arrêt du fallback",
#                     batch_index + 1,
#                     len(batch_opportunities),
#                 )
#                 groq_opportunities = batch_opportunities
#                 break

#             logger.info(
#                 "ℹ️ Lot %d : aucune opportunité éligible", batch_index + 1
#             )

#         # ----------------------------------------------------
#         # Aucun lot n'a pu être analysé (tous en échec réseau/format)
#         # ----------------------------------------------------

#         if not any_groq_success:
#             result = validation_service.fallback_response(filtered_results)
#             elapsed = time.perf_counter() - start_total
#             result["statistics"]["processing_time_seconds"] = round(elapsed, 3)
#             logger.info("🏁 M1 FALLBACK — FIN (%.3fs)", elapsed)
#             return result

#         # ----------------------------------------------------
#         # Tous les lots tentés, mais 0 opportunité au final
#         # ----------------------------------------------------

#         if not groq_opportunities:
#             elapsed = time.perf_counter() - start_total
#             logger.info(
#                 "ℹ️ Aucune opportunité éligible après %d lot(s) testé(s)",
#                 min(MAX_FALLBACK_BATCHES, batch_index + 1),
#             )
#             return {
#                 "opportunities": [],
#                 "market_signals": (
#                     groq_response.get("market_signals", []) if groq_response else []
#                 ),
#                 "total": 0,
#                 "status": "success",
#                 "ai_provider": "groq",
#                 "statistics": {
#                     "raw_results": len(raw_results),
#                     "filtered": len(ranked_results),
#                     "batches_tried": min(MAX_FALLBACK_BATCHES, batch_index + 1),
#                     "groq_results": 0,
#                     "final": 0,
#                     "madagascar": 0,
#                     "processing_time_seconds": round(elapsed, 3),
#                 },
#                 "notes": last_notes or "Aucune opportunité éligible trouvée.",
#             }

#         # ----------------------------------------------------
#         # 5 — NORMALISATION / QUALITÉ / CLASSIFICATION / SCORING
#         # ----------------------------------------------------

#         normalized: List[Dict[str, Any]] = []

#         for opportunity in groq_opportunities:
#             processed = self._process_single_opportunity(opportunity)
#             if processed is not None:
#                 normalized.append(processed)

#         # ----------------------------------------------------
#         # 6 — DÉDUPLICATION + TRI
#         # ----------------------------------------------------

#         normalized = validation_service.deduplicate(normalized)
#         normalized.sort(key=lambda item: int(item.get("score", 0)), reverse=True)

#         # ----------------------------------------------------
#         # 7 — VALIDATION FINALE (schéma Pydantic partagé)
#         # ----------------------------------------------------

#         schema_valid: List[Dict[str, Any]] = []
#         for opportunity in normalized:
#             validated = validation_service.validate_against_schema(opportunity)
#             if validated is not None:
#                 schema_valid.append(validated)

#         # ----------------------------------------------------
#         # 8 — SYNC BACKEND (optionnelle, non bloquante)
#         # ----------------------------------------------------

#         sync_result = await sync_opportunities_to_backend(schema_valid)

#         # ----------------------------------------------------
#         # 9 — STATISTIQUES + RÉPONSE
#         # ----------------------------------------------------

#         madagascar_count = sum(
#             1 for o in schema_valid if o.get("country_scope") == "Madagascar"
#         )

#         elapsed = time.perf_counter() - start_total

#         logger.info("🏁 M1 VEILLE — FIN")
#         logger.info("🔎 Résultats Tavily : %d", len(raw_results))
#         logger.info("🔧 Résultats classés : %d", len(ranked_results))
#         logger.info("🤖 Résultats Groq : %d", len(groq_opportunities))
#         logger.info("✅ Opportunités finales : %d", len(schema_valid))
#         logger.info("🇲🇬 Madagascar : %d", madagascar_count)
#         logger.info("⏱️ Temps total : %.3fs", elapsed)
#         logger.info("=" * 60)

#         return {
#             "opportunities": schema_valid[:20],
#             "market_signals": groq_response.get("market_signals", []),
#             "total": len(schema_valid),
#             "status": "success",
#             "ai_provider": "groq",
#             "statistics": {
#                 "raw_results": len(raw_results),
#                 "filtered": len(ranked_results),
#                 "sources_analyzed": len(filtered_results),
#                 "groq_results": len(groq_opportunities),
#                 "final": len(schema_valid),
#                 "madagascar": madagascar_count,
#                 "backend_sync": sync_result,
#                 "processing_time_seconds": round(elapsed, 3),
#                 # --- Noms explicites (CDC : clarté pour dashboard M8 /
#                 # jury) — mêmes valeurs, libellés sans ambiguïté ---
#                 "prefilter_candidates": len(ranked_results),
#                 "sources_sent_to_llm": len(filtered_results),
#                 "llm_opportunities": len(groq_opportunities),
#                 "final_opportunities": len(schema_valid),
#             },
#             "notes": groq_response.get(
#                 "notes", "Analyse M1 effectuée avec veille.yaml."
#             ),
#         }

#     # ========================================================
#     # HELPER — réponse vide standardisée
#     # ========================================================

#     @staticmethod
#     def _empty_response(
#         status: str,
#         notes: str,
#         elapsed: float = 0.0,
#         raw_count: int = 0,
#     ) -> Dict[str, Any]:
#         return {
#             "opportunities": [],
#             "market_signals": [],
#             "total": 0,
#             "status": status,
#             "ai_provider": None,
#             "statistics": {
#                 "raw_results": raw_count,
#                 "filtered": 0,
#                 "groq_results": 0,
#                 "final": 0,
#                 "madagascar": 0,
#                 "processing_time_seconds": round(elapsed, 3),
#             },
#             "notes": notes,
#         }

#     # ========================================================
#     # ALIAS
#     # ========================================================

#     async def rechercher(self, query: str) -> Dict[str, Any]:
#         return await self.analyser_opportunites(query)