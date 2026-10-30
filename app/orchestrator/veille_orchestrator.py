import asyncio
import io
import logging
import os
import re
import time
from datetime import UTC, datetime
from typing import Any
from urllib.parse import urlparse

import pypdf
from pydantic import ValidationError
from app.schemas.veille import OpportunityResult
from app.orchestrator.base_orchestrator import BaseOrchestrator
from app.orchestrator.base_orchestrator import _vlog as vlog
from app.services.backend_sync import base_sync
from app.services.backend_sync.opportunity_sync import (
    sync_new_opportunities_to_backend,
    sync_opportunities_to_backend,
)
from app.services.hitl.hitl_helper import create_review
from app.services.veille import validation_service
from app.services.veille.classification_service import ClassificationService
from app.services.veille.llm_analysis_service import (
    MAX_SOURCE_CHARS_EACH,
    MAX_SOURCE_CHARS_TOTAL,
    LLMAnalysisService,
)
from app.services.veille.prefilter_service import _TECH_TITLE, diversify_sources, navigation_reason, rank_results, source_domain
from app.utils.url_utils import normalize_url
from app.services.veille.scoring_service import ScoringService
from app.services.veille.tavily_service import SearchResults, TavilySearchError, TavilyService
from app.services.veille.notice_resolution_service import deduplicate_notices
from app.services.veille.progress_service import emit_progress
from app.services.veille.evidence_service import MADAGASCAR, qualify_candidate, source_need
from app.services.veille.source_registry import SEARCH_GROUP, load_registry
from app.services.veille.tavily_quota_service import QuotaTavilyDepasseError

logger = logging.getLogger(__name__)

# ============================================================
# SEUILS — PERMISSIFS
# ============================================================
MIN_SCORE_VALIDATED = int(os.getenv("MIN_SCORE_VALIDATED", "15"))
MIN_SCORE_TO_REVIEW = int(os.getenv("MIN_SCORE_TO_REVIEW", "5"))
MIN_CONFIDENCE_VALIDATED = float(os.getenv("MIN_CONFIDENCE_VALIDATED", "0.10"))
MAX_RESULTS_AI = int(os.getenv("MAX_RESULTS_AI", "8"))
MAX_FALLBACK_BATCHES = int(os.getenv("MAX_FALLBACK_BATCHES", "2"))
# Délai minimal entre deux appels LLM (lots et requêtes enchaînés) :
# évite les 429 Groq (quota tokens/minute). 0 = pas de pause.
VEILLE_PAUSE_LLM_S = max(0.0, float(os.getenv("VEILLE_PAUSE_LLM_S", "0")))
# Garde-fou zone : rejeter toute opportunité sans mention vérifiable de Madagascar
VEILLE_EXIGER_MADAGASCAR = os.getenv("VEILLE_EXIGER_MADAGASCAR", "true").lower() == "true"

# =============================================================================
# GARDE-FOUS DÉTERMINISTES (après le LLM) — le LLM propose, le code vérifie
# =============================================================================
_MOTS_MADAGASCAR = re.compile(
    r"madagascar|malgache|malagasy|antananarivo|tananarive|toamasina|tamatave|"
    r"mahajanga|majunga|fianarantsoa|toliara|tul[ée]ar|antsiranana|di[ée]go[- ]suarez|"
    r"\.mg(?![a-z0-9])",
    re.IGNORECASE,
)


def echeance_depassee(deadline: Any, reference: datetime | None = None) -> bool:
    """True si la date limite (ISO, AAAA-MM-JJ…) est antérieure à la date de référence.
    Date absente ou illisible → False (le scoring la pénalise déjà)."""
    if not deadline:
        return False
    try:
        echeance = datetime.fromisoformat(str(deadline).strip()[:10]).date()
    except ValueError:
        return False
    return echeance < (reference or datetime.now()).date()


def statut_fraicheur(deadline: Any, reference: datetime | None = None) -> str:
    """Classe une opportunité sans laisser le LLM décider de sa fraîcheur."""
    if not deadline:
        return "date_inconnue"
    try:
        limite = datetime.fromisoformat(str(deadline).strip()[:10]).date()
    except ValueError:
        return "date_inconnue"
    jours = (limite - (reference or datetime.now()).date()).days
    if jours < 0:
        return "expirée"
    if jours <= 7:
        return "bientôt_clôturée"
    return "ouverte"


def mentionne_madagascar(opportunity: dict[str, Any]) -> bool:
    """True si Madagascar (pays, ville, gentilé ou domaine .mg) apparaît dans l'opportunité."""
    texte = " ".join(
        str(opportunity.get(champ) or "")
        for champ in ("title", "summary", "organizer", "source", "url", "location")
    )
    return bool(_MOTS_MADAGASCAR.search(texte))


# =============================================================================
# ORCHESTRATEUR
# =============================================================================

class VeilleOrchestrator(BaseOrchestrator):
    """Coordonne le pipeline M1 sans porter lui-même de logique métier."""

    _name = "VeilleOrchestrator"

    def __init__(self):
        vlog("=" * 70)
        vlog("🚀 Initialisation de VeilleOrchestrator (M1)...")
        vlog("=" * 70)

        self.tavily_service = self._safe_init(TavilyService, "TavilyService")
        self.llm_service = self._safe_init(LLMAnalysisService, "LLMAnalysisService")
        self.classification_service = self._safe_init(
            ClassificationService, "ClassificationService"
        )
        self.scoring_service = self._safe_init(ScoringService, "ScoringService")

        self._log_startup_summary({
            "TavilyService":         self.tavily_service,
            "LLMAnalysisService":    self.llm_service,
            "ClassificationService": self.classification_service,
            "ScoringService":        self.scoring_service,
        })

    async def _respecter_pause_llm(self) -> None:
        """Attend si le dernier appel LLM date de moins de VEILLE_PAUSE_LLM_S."""
        if VEILLE_PAUSE_LLM_S > 0:
            dernier = getattr(self, "_dernier_appel_llm", None)
            if dernier is not None:
                reste = VEILLE_PAUSE_LLM_S - (time.monotonic() - dernier)
                if reste > 0:
                    vlog(f"⏸️ Pause LLM {reste:.1f}s (VEILLE_PAUSE_LLM_S)")
                    await asyncio.sleep(reste)
        self._dernier_appel_llm = time.monotonic()

    # ========================================================
    # ENTRÉE 1 — RECHERCHE WEB
    # ========================================================

    async def analyser_opportunites(
        self, query: str, sync_backend: bool = True, categorie: str = "manuel",
        collected_sources: list | None = None,
    ) -> dict[str, Any]:
        """
        Pipeline complet : recherche web → analyse → opportunités.

        sync_backend=False : n'envoie rien au Backend (utilisé par la
        détection automatique, qui synchronise une seule fois à la fin).

        categorie : "auto" | "manuel" | "collecte" — ventile le comptage
        de quota Tavily (Étape B, tavily_quota_service). "manuel" par
        défaut, pour ne rien changer au comportement existant.
        """

        query = str(query or "").strip()
        start_total = time.perf_counter()
        timings = {"source_retrieval_seconds": 0.0, "prefilter_seconds": 0.0,
                   "llm_analysis_seconds": 0.0, "post_processing_seconds": 0.0}
        to_review_candidates: list[dict[str, Any]] = []
        collection_diagnostics = {}

        if not query:
            return self._empty_response(status="error", notes="Requête vide.")

        # Ajout automatique du contexte géographique
        if "madagascar" not in query.lower() and "antananarivo" not in query.lower():
            query = f"{query} Madagascar"
            vlog("🌍 Ajout automatique du contexte géographique")

        vlog("=" * 70)
        vlog("🚀 M1 VEILLE — DÉBUT")
        vlog(f"🔍 Requête : {query}")
        vlog("=" * 70)

        # ── 1. TAVILY (recherche web) ──
        vlog("🌐 [1] Recherche Tavily...")
        if self.tavily_service is None:
            return self._empty_response(status="technical_error", notes="Collecteur M1 indisponible : vérifier la configuration des sources.")
        source_started = time.perf_counter()
        try:
            raw_results = collected_sources if collected_sources is not None else await self.tavily_service.search(query, categorie=categorie)
        except QuotaTavilyDepasseError:
            return self._empty_response(status="quota_atteint", notes="Quota ou limite de débit Tavily atteint.")
        except TavilySearchError as exc:
            timings["source_retrieval_seconds"] = round(time.perf_counter() - source_started, 3)
            return self._empty_response(
                status="technical_error",
                notes="La recherche web n'a pas abouti. Aucun résultat n'est disponible.",
                elapsed=time.perf_counter() - start_total,
                timings=timings,
                technical_reason=str(exc),
                collection_diagnostics=getattr(exc, "diagnostics", {}),
            )
        timings["source_retrieval_seconds"] = round(time.perf_counter() - source_started, 3)
        collection_diagnostics = getattr(raw_results, "diagnostics", {})

        if not raw_results:
            return self._empty_response(
                status="no_results",
                notes="Aucun résultat Tavily.",
                elapsed=time.perf_counter() - start_total,
                timings=timings,
                collection_diagnostics=collection_diagnostics,
            )
        vlog(f"   ✅ {len(raw_results)} résultats bruts")
        source_domains: dict[str, int] = {}
        for raw in raw_results:
            hostname = urlparse(str(raw.get("url", ""))).hostname or "inconnu"
            source_domains[hostname.lower()] = source_domains.get(hostname.lower(), 0) + 1

        # ── 2. CLASSEMENT (préfiltre) ──
        vlog("🏆 [2] Classement (préfiltre)...")
        prefilter_started = time.perf_counter()
        navigation_sources = [{"title": s.get("title"), "url": s.get("url"), "reason": navigation_reason(s)}
                              for s in raw_results if navigation_reason(s)]
        ranked_results = diversify_sources(rank_results([s for s in raw_results if not navigation_reason(s)], query))
        # Une demande effectivement lue passe avant un post riche en hashtags.
        # Le score métier n'est pas modifié ; seul l'ordre d'analyse l'est.
        def analysis_priority(source):
            if source_need(source):
                return 0
            title, path = str(source.get("title", "")), urlparse(str(source.get("url", ""))).path
            if _TECH_TITLE.search(title) and re.search(r"/annonces/|/jobs/view/|/Public/[Nn]otice/", path):
                return 1
            return 2
        ranked_results.sort(key=analysis_priority)
        await emit_progress("analyse", "prefilter", f"Classement : {len(ranked_results)} sources à analyser, {len(navigation_sources)} pages générales mises à part.",
                            selected=len(ranked_results), navigation=len(navigation_sources))
        timings["prefilter_seconds"] = round(time.perf_counter() - prefilter_started, 3)

        if not ranked_results:
            empty = self._empty_response(
                status="no_results",
                notes="Aucun résultat après préfiltrage.",
                elapsed=time.perf_counter() - start_total,
                raw_count=len(raw_results),
                timings=timings,
                collection_diagnostics=collection_diagnostics,
            )
            empty["navigation_sources"] = navigation_sources
            if navigation_sources:
                empty.update(status="partial", notes="Pages de navigation collectées, aucune annonce individuelle qualifiable. Aucun appel Groq nécessaire.")
            return empty
        vlog(f"   ✅ {len(ranked_results)} résultats après préfiltre")
        source_records = [
            {"title": str(item.get("title", "")), "url": str(item.get("url", "")),
             "domain": source_domain(str(item.get("url", ""))),
             "prefilter_score": item.get("prefilter_score"),
             "analysis_status": "pending", "reason": None, "reason_origin": None,
             "final_status": "not_evaluated", "final_reason": None}
            for item in ranked_results
        ]

        def attach_source_diagnostics(result):
            """Rend les preuves consultables sans promouvoir des candidats."""
            result["analyzed_sources"] = [
                item for item in source_records
                if item["analysis_status"] in {"rejected", "proposed", "undecided"}
            ]
            result["pending_sources"] = [
                item for item in source_records
                if item["analysis_status"] in {"pending", "failed", "quota_atteint"}
            ]
            from app.services.veille.pending_service import save
            pending_urls = {item["url"] for item in result["pending_sources"]}
            result["continuation_id"] = save([s for s in ranked_results if s.get("url") in pending_urls], query)
            stats = result.setdefault("statistics", {})
            stats["sources_analyzed"] = len(result["analyzed_sources"])
            stats["sources_unanalyzed"] = len(result["pending_sources"])
            stats["sources_sent_to_llm"] = sources_attempted
            result["to_review_candidates"] = to_review_candidates
            stats["candidates_to_review"] = len(to_review_candidates)
            stats["llm_candidates_proposed"] = proposed_count
            stats["documented_candidates"] = len(groq_opportunities)
            stats["confirmed_opportunities"] = result.get("total", 0)
            stats["groq_results"] = proposed_count
            result["collection_diagnostics"] = collection_diagnostics
            result["navigation_sources"] = navigation_sources
            stats["navigation_pages_skipped"] = len(navigation_sources)
            stats["llm_batches_attempted"] = len(batch_reports)
            result["analysis_batches"] = batch_reports
            incomplete_domains = [d for d in collection_diagnostics.get("domain_coverage", [])
                                  if d.get("status") in {"failed", "not_searched"}]
            if incomplete_domains and result.get("status") in {"success", "no_results"}:
                result["status"] = "partial"
            for record in result["analyzed_sources"]:
                candidate = next((c for c in to_review_candidates if normalize_url(c.get("url")) == normalize_url(record["url"])), None)
                if candidate:
                    record.update(final_status="to_review", final_reason=candidate["ai_recommendation"])
                elif record["analysis_status"] == "rejected":
                    record.update(final_status="rejected", final_reason=record["reason"])
            result["search_group"] = SEARCH_GROUP.get() or "institutionnel"
            result["next_step"] = "verify_source" if to_review_candidates else (
                "analyze_pending" if result["pending_sources"] else "review_results")
            if to_review_candidates and result.get("status") == "no_results":
                result["status"] = "partial"
            if result.get("status") == "partial":
                result["notes"] = (
                    f"Analyse incomplète : {stats['sources_analyzed']} source(s) analysée(s), "
                    f"{stats['sources_unanalyzed']} source(s) non analysée(s), "
                    f"{len(to_review_candidates)} candidat(s) à vérifier. "
                    f"{result.get('total', 0)} opportunité(s) confirmée(s). "
                    f"{len(incomplete_domains)} site(s) avec recherche ciblée non aboutie."
                )
            return result

        # ── 3/4. ANALYSE LLM PAR LOTS ──
        vlog(f"🤖 [3] Analyse LLM (max {MAX_FALLBACK_BATCHES} lot(s))...")
        groq_response = None
        groq_opportunities: list[dict[str, Any]] = []
        filtered_results: list[dict[str, Any]] = []
        last_notes = None
        any_groq_success = False
        failed_batches = 0
        sources_analyzed = 0
        sources_attempted = 0
        grounded_by_url: dict[str, dict[str, Any]] = {}
        batch_index = 0
        proposed_count = 0
        batch_reports = []

        for batch_index in range(MAX_FALLBACK_BATCHES):
            start_idx = batch_index * MAX_RESULTS_AI
            end_idx = start_idx + MAX_RESULTS_AI
            batch = ranked_results[start_idx:end_idx]

            if not batch:
                break

            vlog(
                f"🔁 Lot {batch_index + 1}/{MAX_FALLBACK_BATCHES} : "
                f"{len(batch)} source(s)"
            )

            await self._respecter_pause_llm()
            llm_started = time.perf_counter()
            await emit_progress("analyse", "llm_analysis", f"Analyse IA du lot {batch_index + 1} : {len(batch)} source(s).",
                                batch=batch_index + 1, sources=len(batch))
            batch_response = await self.llm_service.analyze(query, batch, compact=True)
            await emit_progress("analyse", "verification", "Contrôle des preuves, de la fraîcheur et du score métier.")
            batch_reports.append({"sources": len(batch), "status": (batch_response or {}).get("status", "success" if batch_response else "failed"),
                                  "prompt_characters": (batch_response or {}).get("prompt_characters"),
                                  "usage": (batch_response or {}).get("llm_usage", {})})
            sources_attempted += len(batch)
            timings["llm_analysis_seconds"] += round(time.perf_counter() - llm_started, 3)
            filtered_results = batch

            if batch_response is None:
                failed_batches += 1
                for record in source_records[start_idx:end_idx]:
                    record.update(analysis_status="failed", reason="Analyse indisponible ; à réessayer.",
                                  reason_origin="system")
                logger.warning(
                    f"⚠️ Lot {batch_index + 1} : analyse Groq échouée, "
                    f"passage au lot suivant"
                )
                continue

            if batch_response.get("status") == "quota_atteint":
                for record in source_records[start_idx:end_idx]:
                    record.update(analysis_status="quota_atteint", reason="Quota Groq atteint.",
                                  reason_origin="system")
                return attach_source_diagnostics({"opportunities": [], "total": 0, "status": "quota_atteint",
                        "notes": batch_response.get("notes"),
                        "statistics": {"sources_analyzed": sources_analyzed,
                                       "sources_attempted": sources_attempted,
                                       "raw_results": len(raw_results), **timings}})

            any_groq_success = True
            submitted_count = batch_response.get("sources_submitted", len(batch))
            if type(submitted_count) is not int or not 0 <= submitted_count <= len(batch):
                submitted_count = 0
            sources_attempted -= len(batch) - submitted_count
            sources_analyzed += submitted_count
            rejected = {}
            for rejection in batch_response.get("rejets", []) or []:
                if not isinstance(rejection, dict):
                    continue
                number = rejection.get("resultat")
                reason = rejection.get("raison")
                if type(number) is int and 1 <= number <= submitted_count and isinstance(reason, str):
                    rejected[number] = reason
            proposed_urls = {
                normalize_url(item.get("url")) for item in batch_response.get("opportunities", [])
                if isinstance(item, dict) and item.get("url")
            }
            for number, record in enumerate(source_records[start_idx:start_idx + submitted_count], 1):
                record["reason_origin"] = "groq"
                if normalize_url(record["url"]) in proposed_urls:
                    record.update(analysis_status="proposed",
                                  reason="Candidat proposé par Groq ; soumis aux validations Python.")
                elif number in rejected:
                    record.update(analysis_status="rejected", reason=rejected[number])
                    reason = rejected[number]
                    unsupported = re.search(r"hors\s+(?:l['’])?ia\b|non li[ée].*\bia\b|pas d.appel d.offres officiel", reason, re.I)
                    other_ground = re.search(r"expir|hors madagascar|publicit|emploi salari|\bcdi\b|\bcdd\b", reason, re.I)
                    source = batch[number - 1]
                    if unsupported and not other_ground and _TECH_TITLE.search(str(source.get("title", "")) + " " + str(source.get("content", ""))):
                        message = "Motif de rejet insuffisant : ALTIORA couvre l'informatique au-delà de l'IA et les demandes privées de prestation. Vérifier le besoin client, la localisation, l'échéance et le statut externe."
                        to_review_candidates.append({"title": source.get("title"), "url": source.get("url"),
                            "status": "to_review", "verification_status": "to_review", "review_reason": "unsupported_rejection",
                            "is_actionable": False, "score": 0, "score_evaluated": False, "score_label": "Non évalué",
                            "ai_recommendation": message, "ai_points_to_verify": [reason, "Demande de prestation externe et conditions à vérifier"],
                            "next_step": "verify_source"})
                else:
                    record.update(analysis_status="undecided",
                                  reason="Groq n'a pas fourni de décision explicite pour cette source.")
            groq_response = batch_response
            last_notes = batch_response.get("notes")
            batch_opportunities = batch_response.get("opportunities", [])
            proposed_count += sum(isinstance(item, dict) for item in batch_opportunities)
            qualified = []
            for proposal in batch_opportunities:
                if not isinstance(proposal, dict):
                    continue
                grounded, gaps = qualify_candidate(proposal, batch[:submitted_count])
                grounded_by_url[normalize_url(grounded.get("url"))] = grounded
                if gaps:
                    to_review_candidates.append(grounded)
                else:
                    qualified.append(grounded)
            batch_opportunities = qualified

            if batch_opportunities:
                groq_opportunities.extend(batch_opportunities)
                if all(echeance_depassee(item.get("deadline")) for item in batch_opportunities):
                    vlog(f"ℹ️ Lot {batch_index + 1} : candidats expirés ; examen du lot suivant")
                    continue
                vlog(
                    f"✅ Lot {batch_index + 1} : "
                    f"{len(batch_opportunities)} opportunité(s) — arrêt"
                )
                break

            vlog(f"ℹ️ Lot {batch_index + 1} : aucune opportunité éligible")

        # ── CAS A : Aucun lot analysé ──
        if not any_groq_success:
            result = validation_service.fallback_response(filtered_results)
            elapsed = time.perf_counter() - start_total
            result["statistics"]["processing_time_seconds"] = round(elapsed, 3)
            result["statistics"].update(timings)
            result["statistics"].update(raw_results=len(raw_results), filtered=len(ranked_results))
            vlog(f"🏁 M1 FALLBACK — FIN ({elapsed:.3f}s)")
            return attach_source_diagnostics(result)

        # ── CAS B : Tous les lots tentés, 0 opportunité ──
        if not groq_opportunities:
            elapsed = time.perf_counter() - start_total
            vlog(
                f"ℹ️ Aucune opportunité éligible après "
                f"{min(MAX_FALLBACK_BATCHES, batch_index + 1)} lot(s)"
            )
            return attach_source_diagnostics({
                "opportunities": [],
                "market_signals": (
                    groq_response.get("market_signals", []) if groq_response else []
                ),
                "total": 0,
                "status": "partial" if failed_batches or sources_analyzed < len(ranked_results) else "no_results",
                "ai_provider": "groq",
                "statistics": {
                    "raw_results": len(raw_results),
                    "filtered": len(ranked_results),
                    "batches_tried": min(MAX_FALLBACK_BATCHES, batch_index + 1),
                    "groq_results": 0,
                    "final": 0,
                    "madagascar": 0,
                    "processing_time_seconds": round(elapsed, 3),
                    "source_domains": source_domains,
                    "sources_analyzed": sources_analyzed,
                    "sources_attempted": sources_attempted,
                    "sources_unanalyzed": len(ranked_results) - sources_analyzed,
                    "failed_batches": failed_batches,
                    **timings,
                },
                "notes": (
                    "Analyse incomplète : certaines sources restent à analyser ou ont échoué. "
                    "Aucune opportunité confirmée dans les sources analysées."
                    if failed_batches or sources_analyzed < len(ranked_results)
                    else last_notes or "Aucune opportunité éligible trouvée."
                ),
            })

        # ── 5→9. POST-TRAITEMENT COMMUN ──
        post_started = time.perf_counter()
        result = await self._finalize_opportunities(
            groq_opportunities=groq_opportunities,
            groq_response=groq_response or {},
            start_total=start_total,
            extra_statistics={
                "raw_results": len(raw_results),
                "filtered": len(ranked_results),
                "sources_analyzed": len(filtered_results),
                "prefilter_candidates": len(ranked_results),
                "sources_sent_to_llm": len(filtered_results),
                "source_domains": source_domains,
            },
            sync_backend=False,
            real_evidence=True,
        )
        # Les critères de preuve et de pertinence du chemin réel sont plus
        # stricts que les anciens seuils permissifs du traitement commun.
        confirmed = []
        for opportunity in result.get("opportunities", []):
            grounded = grounded_by_url.get(normalize_url(opportunity.get("url")), {})
            valid_shape = True
            try:
                OpportunityResult.model_validate(opportunity)
            except ValidationError:
                valid_shape = False
            if opportunity.get("score", 0) < 40 or not valid_shape:
                candidate = {**opportunity, **grounded, "status": "to_review", "is_actionable": False,
                             "score": opportunity.get("score", 0),
                             "reason": opportunity.get("reason"), "score_evaluated": True,
                             "ai_risk_level": "élevé", "next_step": "verify_source",
                             "ai_recommendation": "Vérifier l'adéquation du besoin aux services ALTIORA avant de préparer une offre.",
                             "ai_points_to_verify": [f"Score métier {opportunity.get('score', 0)}/100 (seuil 40) ; conformité du résultat : {valid_shape}"]}
                to_review_candidates.append(candidate)
                continue
            opportunity.update({key: grounded.get(key) for key in (
                "evidence", "evidence_origin", "source_title", "published_at", "captured_at", "last_checked_at",
                "last_verified_at", "verification_method", "verification_status", "next_step",
                "ai_recommendation", "ai_points_to_verify", "ai_risk_level", "reference")})
            opportunity.update({key: grounded[key] for key in (
                "deadline_at", "deadline_precision", "deadline_timezone", "freshness_status", "score_evaluated")
                if key in grounded})
            confirmed.append(opportunity)
        result["opportunities"] = confirmed
        result["total"] = len(confirmed)
        result["statistics"]["final"] = len(confirmed)
        result["statistics"]["final_opportunities"] = len(confirmed)
        result["statistics"]["madagascar"] = sum(o.get("country_scope") == "Madagascar" for o in confirmed)
        if sync_backend and confirmed:
            review_id = create_review(
                agent_id="agent_m1_veille", data={"opportunities": confirmed},
                summary=f"M1 réel — {len(confirmed)} opportunité(s) documentée(s)", criticity="medium",
            )
            result.update(_review_id=review_id, _review_status="pending_review")
            result["statistics"]["backend_sync"]["review_id"] = review_id
        if not confirmed:
            result["status"] = "no_results"
        timings["post_processing_seconds"] = round(time.perf_counter() - post_started, 3)
        result["statistics"].update(timings)
        result["statistics"].update({
            "sources_analyzed": sources_analyzed,
            "sources_attempted": sources_attempted,
            "sources_unanalyzed": len(ranked_results) - sources_analyzed,
            "failed_batches": failed_batches,
        })
        if failed_batches or sources_analyzed < len(ranked_results):
            result["status"] = "partial"
        retained_urls = {normalize_url(item.get("url")) for item in result.get("opportunities", [])}
        proposals = {normalize_url(item.get("url")): item for item in groq_opportunities
                     if isinstance(item, dict) and item.get("url")}
        for record in source_records:
            if record["analysis_status"] != "proposed":
                continue
            url = normalize_url(record["url"])
            candidate = next((c for c in to_review_candidates if normalize_url(c.get("url")) == url), None)
            if candidate:
                record.update(final_status="to_review", final_reason=candidate["ai_recommendation"])
                continue
            if url in retained_urls:
                record.update(final_status="retained", final_reason="Validations Python réussies.")
            else:
                proposal = proposals.get(url, {})
                deadline = proposal.get("deadline")
                reason = (f"Échéance extraite dépassée ({deadline})." if echeance_depassee(deadline)
                          else "Candidat non retenu après les validations Python.")
                record.update(final_status="rejected", final_reason=reason)
        return attach_source_diagnostics(result)

    # ========================================================
    # ENTRÉE 1 bis — DÉTECTION AUTOMATIQUE (sans requête saisie)
    # ========================================================

    async def _detecter_collecte_dabord(self, queries, min_score, limit, sync_backend,
                                      source_groups, budget_seconds, categorie):
        """Collecte toutes les familles prévues avant une analyse globale bornée."""
        if self.tavily_service is None:
            return self._empty_response("technical_error", "Collecteur M1 indisponible : vérifier le registre des sources.")
        started = time.perf_counter()
        registry = load_registry()
        active = [g.id for g in registry.groups if any(s.enabled for s in g.sources)]
        if "missions_privees" in active:
            active.insert(1, active.pop(active.index("missions_privees")))
        plan = source_groups or [active[i % len(active)] for i in range(len(queries))]
        if len(plan) != len(queries) or any(group not in active for group in plan):
            raise ValueError("Une famille active est requise pour chaque requête.")
        budget = max(1, budget_seconds if budget_seconds is not None else float(os.getenv("M1_DETECTION_BUDGET_S", "90")))
        reserve = min(25, budget / 3)
        records, collected = [None] * len(queries), []
        diagnostics = {"attempts": [], "domain_coverage": [], "notice_resolution": []}
        quota_stop = asyncio.Event()
        semaphore = asyncio.Semaphore(2)
        async def collect(index, query, family):
            async with semaphore:
                remaining = budget - reserve - (time.perf_counter() - started)
                if quota_stop.is_set() or remaining <= 0:
                    records[index] = {"query": query, "source_group": family,
                                      "status": "quota_atteint" if quota_stop.is_set() else "technical_error",
                                      "skipped": True, "error": "quota" if quota_stop.is_set() else "collection_time_budget", "found": 0}
                    return
                token = SEARCH_GROUP.set(family)
                detail = {}
                try:
                    await emit_progress("requete", "collection_started", f"Recherche {index + 1}/{len(queries)} — {family} : {query}",
                                        numero=index + 1, total=len(queries), query=query, family=family)
                    async with asyncio.timeout(remaining):
                        sources = await self.tavily_service.search(query, categorie=categorie)
                    collected.extend(sources)
                    detail = getattr(sources, "diagnostics", {})
                    records[index] = {"query": query, "source_group": family, "status": "collected", "found": 0,
                                      "collection_diagnostics": detail, "statistics": {"raw_results": len(sources)}}
                    await emit_progress("analyse", "collection_completed", f"{family} : {len(sources)} document(s) collecté(s), qualification à effectuer.",
                                        family=family, collected=len(sources))
                    for source in sources:
                        await emit_progress("analyse", "source_collected", f"Source collectée — {source.get('title', '')}", family=family,
                                            source={key: source.get(key) for key in ("title", "url", "captured_at", "published_at", "last_verified_at")},
                                            verification_status="collected_not_qualified")
                except QuotaTavilyDepasseError:
                    quota_stop.set()
                    records[index] = {"query": query, "source_group": family, "status": "quota_atteint", "found": 0}
                    await emit_progress("analyse", "collection_limited", f"{family} : quota de recherche atteint.", family=family)
                except (TavilySearchError, TimeoutError) as exc:
                    detail = getattr(exc, "diagnostics", {})
                    records[index] = {"query": query, "source_group": family, "status": "technical_error", "found": 0,
                                      "collection_diagnostics": detail, "error": type(exc).__name__}
                    await emit_progress("analyse", "collection_failed", f"{family} : collecte incomplète, les autres résultats seront conservés.", family=family)
                finally:
                    for key in diagnostics:
                        diagnostics[key].extend({**item, "family": family} for item in detail.get(key, []))
                    SEARCH_GROUP.reset(token)
        await asyncio.gather(*(collect(i, q, f) for i, (q, f) in enumerate(zip(queries, plan))))
        collection_elapsed = time.perf_counter() - started
        remaining = budget - collection_elapsed
        token = SEARCH_GROUP.set("all")
        try:
            if remaining <= 0:
                result = self._empty_response("technical_error", "Budget épuisé avant l'analyse ; collecte conservée dans les diagnostics.")
            else:
                async with asyncio.timeout(remaining):
                    result = await self.analyser_opportunites(
                        " ; ".join(dict.fromkeys(queries)), sync_backend=False, categorie=categorie,
                        collected_sources=SearchResults(deduplicate_notices(collected), diagnostics))
        except TimeoutError:
            result = self._empty_response("partial", "Analyse interrompue par le budget ; consulter les sources collectées.")
        finally:
            SEARCH_GROUP.reset(token)
        result.setdefault("collection_diagnostics", diagnostics)
        if result.get("status") in {"technical_error", "partial"} and not result.get("analyzed_sources") and not result.get("pending_sources"):
            result["pending_sources"] = [{"title": s.get("title"), "url": s.get("url"), "analysis_status": "pending",
                                          "reason": "Analyse non aboutie dans le budget", "domain": source_domain(s.get("url", ""))}
                                         for s in collected if not navigation_reason(s)]
        documented = result.get("opportunities", [])
        eligible = [o for o in documented if o.get("score", 0) >= min_score]
        eligible.sort(key=lambda opportunity: opportunity.get("score", 0), reverse=True)
        final = eligible[:limit]
        retained_urls = {o.get("url") for o in final}
        for record in result.get("analyzed_sources", []):
            candidate = next((o for o in documented if o.get("url") == record.get("url")), None)
            if candidate and candidate.get("url") not in retained_urls:
                record.update(final_status="filtered_score" if candidate.get("score", 0) < min_score else "filtered_limit",
                              final_reason=f"Score {candidate.get('score', 0)}/100 ; seuil demandé {min_score}, limite {limit}.")
        stats = result.setdefault("statistics", {})
        stats.update(final=len(final), final_opportunities=len(final), confirmed_opportunities=len(final),
                     madagascar=sum(o.get("country_scope") == "Madagascar" for o in final),
                     below_requested_score=len(documented) - len(eligible), omitted_by_limit=len(eligible) - len(final),
                     collection_concurrency=2,
                     queries_run=sum(not r.get("skipped") for r in records), queries_planned=len(queries),
                     collected_documents=len(collected), source_retrieval_seconds=round(collection_elapsed, 3),
                     processing_time_seconds=round(time.perf_counter() - started, 3))
        if sync_backend and final:
            stats["backend_sync"] = await sync_new_opportunities_to_backend(final)
        else:
            stats["backend_sync"] = {"enabled": base_sync.is_sync_enabled(), "sent": 0, "failed": 0, "deferred": not sync_backend}
        incomplete = any(r["status"] != "collected" for r in records)
        if incomplete and result.get("status") in {"success", "no_results"}:
            result["status"] = "partial"
        if not collected and all(r["status"] in {"technical_error", "quota_atteint"} for r in records):
            result["status"] = "quota_atteint" if quota_stop.is_set() else "technical_error"
        for record in records:
            record["found"] = sum(o.get("url") in {
                s.get("url") for s in collected if s.get("search_group") == record["source_group"]} for o in final)
        result.update(mode="automatique", opportunities=final, total=len(final), queries=records,
                      collection_complete=not incomplete, analysis_strategy="collect_then_analyze",
                      source_groups=[{"family": group, "domains": registry.domains(group), "planned": group in plan,
                                      "executed": any(r["source_group"] == group and not r.get("skipped") for r in records),
                                      "statuses": [r["status"] for r in records if r["source_group"] == group]} for group in active])
        result["notes"] = (f"Collecte : {stats['queries_run']}/{len(queries)} requête(s) exécutée(s). "
                           f"{len(final)} opportunité(s) confirmée(s), "
                           f"{len(result.get('to_review_candidates', []))} candidat(s) à vérifier, "
                           f"{len(result.get('pending_sources', []))} source(s) non analysée(s). "
                           f"{stats['below_requested_score']} écartée(s) par le seuil demandé de {min_score}. "
                           f"Statut : {result.get('status')}.")
        for source in result.get("analyzed_sources", []):
            await emit_progress("analyse", "source_decision", f"{source.get('title', '')} — {source.get('final_status', '')} : {source.get('final_reason') or source.get('reason') or ''}",
                                source=source)
        await emit_progress("analyse", "ranking_completed", f"Classement terminé : {len(final)} opportunité(s) retenue(s), recommandations disponibles.", total=len(final))
        return result

    async def detecter_automatiquement(
        self,
        queries: list[str],
        min_score: int = 40,
        limit: int = 20,
        sync_backend: bool = True,
        source_groups: list[str] | None = None,
        budget_seconds: float | None = None,
        categorie: str = "auto",
        collect_first: bool = False,
    ) -> dict[str, Any]:
        """
        Détection sans requête utilisateur : exécute la série de requêtes
        `queries` (profil ALTIORA, cf. auto_detection_service), fusionne les
        résultats, retire les doublons, ne garde que score >= min_score, puis
        synchronise UNE fois vers le Backend en ignorant ce qui y existe déjà.

        Les requêtes sont exécutées l'une après l'autre (quotas Tavily/Groq).
        Une requête en échec n'interrompt pas les suivantes.
        """
        start_total = time.perf_counter()
        queries = [str(q).strip() for q in (queries or []) if str(q).strip()]

        if not queries:
            return self._empty_response(
                status="error", notes="Aucune requête de détection configurée."
            )

        if collect_first:
            return await self._detecter_collecte_dabord(
                queries, min_score, limit, sync_backend, source_groups, budget_seconds, categorie)

        vlog("=" * 70)
        vlog(f"🤖 M1 DÉTECTION AUTOMATIQUE — DÉBUT ({len(queries)} requête(s))")
        vlog("=" * 70)

        par_requete: list[dict[str, Any]] = []
        collectees: list[dict[str, Any]] = []
        analyzed_sources: list[dict[str, Any]] = []
        pending_sources: list[dict[str, Any]] = []
        to_review_candidates: list[dict[str, Any]] = []
        registry = load_registry()
        group_ids = [g.id for g in registry.groups if any(s.enabled for s in g.sources)]
        if "missions_privees" in group_ids:
            group_ids.insert(1, group_ids.pop(group_ids.index("missions_privees")))
        if source_groups:
            if len(source_groups) != len(queries) or any(g not in group_ids for g in source_groups):
                raise ValueError("Une famille active est requise pour chaque requête.")
        planned_groups = source_groups or [group_ids[i % len(group_ids)] for i in range(len(queries))]
        run_budget = max(1.0, budget_seconds if budget_seconds is not None else float(os.getenv("M1_DETECTION_BUDGET_S", "90")))

        def append_skipped(status, reason):
            for index in range(len(par_requete), len(queries)):
                par_requete.append({"query": queries[index], "source_group": planned_groups[index],
                                    "status": status, "found": 0, "skipped": True, "error": reason})

        for query in queries:
            selected_group = planned_groups[len(par_requete)]
            token = SEARCH_GROUP.set(selected_group)
            try:
                remaining = run_budget - (time.perf_counter() - start_total)
                if remaining <= 0:
                    raise TimeoutError
                async with asyncio.timeout(remaining):
                    resultat = await self.analyser_opportunites(
                        query, sync_backend=False, categorie=categorie
                    )
            except QuotaTavilyDepasseError:
                resultat = {"opportunities": [], "status": "quota_atteint"}
            except TimeoutError:
                append_skipped("technical_error", "time_budget_exceeded")
                break
            except Exception as exc:
                logger.exception("❌ Détection auto — requête en échec : %s", query)
                par_requete.append({
                    "query": query, "status": "error",
                    "found": 0, "error": type(exc).__name__, "source_group": selected_group,
                })
                continue
            finally:
                SEARCH_GROUP.reset(token)

            trouvees = [
                o for o in resultat.get("opportunities", []) if isinstance(o, dict)
            ]
            analyzed_sources.extend({**item, "query": query} for item in resultat.get("analyzed_sources", []))
            pending_sources.extend({**item, "query": query} for item in resultat.get("pending_sources", []))
            to_review_candidates.extend(resultat.get("to_review_candidates", []))
            par_requete.append({
                "query": query,
                "status": resultat.get("status"),
                "found": len(trouvees),
                "source_group": resultat.get("search_group", selected_group),
                "collection_diagnostics": resultat.get("collection_diagnostics", {}),
                "statistics": {key: (resultat.get("statistics") or {}).get(key, 0)
                               for key in ("raw_results", "filtered", "sources_sent_to_llm")},
            })
            for opportunite in trouvees:
                opportunite["detected_by_query"] = query
            collectees.extend(trouvees)
            if resultat.get("status") == "quota_atteint":
                # Ne pas relancer Groq pour les requêtes restantes du même passage.
                append_skipped("quota_atteint", "quota_atteint")
                break

        # ── FUSION : meilleur score d'abord, puis dédoublonnage URL/titre ──
        collectees.sort(key=lambda o: int(o.get("score", 0) or 0), reverse=True)
        uniques = validation_service.deduplicate(collectees)
        retenues = [o for o in uniques if int(o.get("score", 0) or 0) >= min_score]
        finales = retenues[:limit]

        # ── SYNC BACKEND (une fois, sans doublons) ──
        if sync_backend and finales:
            sync_result = await sync_new_opportunities_to_backend(finales)
        else:
            sync_result = {
                "enabled": base_sync.is_sync_enabled(),
                "sent": 0,
                "failed": 0,
                "already_present": 0,
                "deferred": not sync_backend,
            }

        ok = [r for r in par_requete if r["status"] in ("success", "no_results", "partial")]
        if not ok:
            statut = "quota_atteint" if any(r["status"] == "quota_atteint" for r in par_requete) else "technical_error"
        elif len(ok) < len(par_requete) or any(r["status"] == "partial" for r in par_requete):
            statut = "partial"
        else:
            statut = "success"
        if statut == "success" and not finales:
            statut = "no_results"

        elapsed = time.perf_counter() - start_total
        vlog(
            f"🏁 M1 DÉTECTION AUTOMATIQUE — FIN ({elapsed:.1f}s) : "
            f"{len(finales)} opportunité(s), statut={statut}"
        )

        return {
            "mode": "automatique",
            "opportunities": finales,
            "market_signals": [],
            "total": len(finales),
            "status": statut,
            "ai_provider": "groq",
            "queries": par_requete,
            "source_groups": [{"family": group, "domains": registry.domains(group),
                               "planned": group in planned_groups,
                               "executed": any(q.get("source_group") == group and not q.get("skipped") for q in par_requete),
                               "statuses": [q["status"] for q in par_requete if q.get("source_group") == group]}
                              for group in group_ids],
            "analyzed_sources": analyzed_sources,
            "pending_sources": pending_sources,
            "to_review_candidates": to_review_candidates,
            "statistics": {
                "sources_analyzed": len(analyzed_sources),
                "sources_unanalyzed": len(pending_sources),
                "raw_results": sum(q.get("statistics", {}).get("raw_results", 0) for q in par_requete),
                "sources_sent_to_llm": sum(q.get("statistics", {}).get("sources_sent_to_llm", 0) for q in par_requete),
                "queries_run": sum(not q.get("skipped", False) for q in par_requete),
                "queries_planned": len(queries),
                "collected": len(collectees),
                "after_dedup": len(uniques),
                "below_min_score": len(uniques) - len(retenues),
                "final": len(finales),
                "min_score": min_score,
                "backend_sync": sync_result,
                "processing_time_seconds": round(elapsed, 3),
            },
            "notes": (
                f"Détection automatique : {len(finales)} opportunité(s) "
                f"(score >= {min_score}) sur {len(queries)} requête(s)."
            ),
        }

    # ========================================================
    # ENTRÉE 2 — TEXTE COLLÉ
    # ========================================================

    async def analyser_texte(
        self,
        texte: str,
        source: str = "manuel",
        sync_backend: bool = True,
        date_reference: datetime | None = None,
    ) -> dict[str, Any]:
        """Pipeline : texte collé → analyse directe (sans recherche web).

        sync_backend=False : n'envoie rien au Backend (utilisé par le
        benchmark M1 — correction 1c, mission "Étape 1" : lancer le
        benchmark sur le corpus annoté ne doit jamais polluer la base
        formaia avec de fausses opportunités).

        date_reference : date à laquelle évaluer le score (Étape C,
        mission "Préparation soutenance" — reproductibilité). Le
        benchmark passe la date de collecte de chaque document ; sans
        cela, rejouer le même corpus à des dates différentes donnerait
        des scores différents (ScoringService évalue l'échéance par
        rapport à "maintenant")."""

        texte = str(texte or "").strip()
        source_label = str(source or "manuel").strip() or "manuel"
        start_total = time.perf_counter()

        if not texte:
            return self._empty_response(status="error", notes="Texte vide.")

        vlog("=" * 70)
        vlog(f"🚀 M1 ANALYSE TEXTE — DÉBUT (source: {source_label})")
        vlog(f"📄 Longueur : {len(texte)} caractères")
        vlog("=" * 70)

        pseudo_sources = self._split_texte_en_sources(texte, source_label)

        instruction = (
            f"Analyse directe d'un document fourni par l'utilisateur "
            f"(source : {source_label}). Pas de recherche web associée."
        )

        groq_response = await self.llm_service.analyze(
            query=instruction,
            results=pseudo_sources,
            date_reference=date_reference,
        )

        if groq_response is None:
            result = validation_service.fallback_response(pseudo_sources)
            elapsed = time.perf_counter() - start_total
            result["statistics"]["processing_time_seconds"] = round(elapsed, 3)
            vlog(f"🏁 M1 ANALYSE TEXTE FALLBACK — FIN ({elapsed:.3f}s)")
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
            sync_backend=sync_backend,
            date_reference=date_reference,
        )

    @staticmethod
    def _split_texte_en_sources(
        texte: str, source_label: str
    ) -> list[dict[str, Any]]:
        """Découpe un texte long en plusieurs blocs 'source'."""
        chunks: list[dict[str, Any]] = []
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
            chunks.append({
                "title": source_label,
                "url": "",
                "content": texte[:MAX_SOURCE_CHARS_EACH],
            })

        if len(texte) > total_chars:
            logger.warning(
                f"✂️ Texte tronqué : {total_chars}/{len(texte)} caractères "
                f"envoyés à Groq"
            )

        return chunks

    # ========================================================
    # ENTRÉE 3 — ANALYSE PDF
    # ========================================================

    @staticmethod
    def _extract_pdf_text(pdf_bytes: bytes) -> str:
        """Extrait le texte d'un PDF (PyPDF2, même logique que la route
        /ia/veille/analyser-pdf qui fait sa propre extraction en pratique)."""
        reader = pypdf.PdfReader(io.BytesIO(pdf_bytes))
        pages = []
        for page in reader.pages:
            text = (page.extract_text() or "").strip()
            if text:
                pages.append(text)
        return "\n\n".join(pages)

    async def analyser_pdf(
        self, pdf_bytes: bytes, filename: str = "document.pdf"
    ) -> dict[str, Any]:
        """
        Pipeline : PDF → extraction texte → analyse IA.

        Args:
            pdf_bytes: Contenu binaire du fichier PDF.
            filename: Nom du fichier (pour logs).

        Returns:
            Dict avec opportunités (même format que analyser_texte).
        """
        start_total = time.perf_counter()

        if not pdf_bytes:
            return self._empty_response(status="error", notes="PDF vide.")

        vlog("=" * 70)
        vlog(f"🚀 M1 ANALYSE PDF — DÉBUT ({filename})")
        vlog(f"📄 Taille : {len(pdf_bytes):,} bytes")
        vlog("=" * 70)

        # ── ÉTAPE 1 : EXTRACTION TEXTE ──
        try:
            vlog("📄 [1/2] Extraction du texte...")
            texte = self._extract_pdf_text(pdf_bytes)

            if not texte or not texte.strip():
                return self._empty_response(
                    status="no_results",
                    notes="Aucun texte extrait du PDF.",
                    elapsed=time.perf_counter() - start_total,
                )

            vlog(f"   ✅ {len(texte):,} caractères extraits")

        except Exception as e:
            logger.error(f"❌ Erreur extraction PDF : {e}")
            return self._empty_response(
                status="error",
                notes=f"Erreur extraction PDF : {e}",
                elapsed=time.perf_counter() - start_total,
            )

        # ── ÉTAPE 2 : ANALYSE IA (réutilise analyser_texte) ──
        vlog("🤖 [2/2] Analyse IA du texte extrait...")
        result = await self.analyser_texte(texte, source=filename)

        elapsed = time.perf_counter() - start_total
        result["statistics"]["pdf_filename"] = filename
        result["statistics"]["pdf_size_bytes"] = len(pdf_bytes)
        result["statistics"]["total_processing_seconds"] = round(elapsed, 3)

        vlog("=" * 70)
        vlog(f"🏁 M1 ANALYSE PDF — FIN ({elapsed:.3f}s)")
        vlog(f"   📊 Opportunités : {result.get('total', 0)}")
        vlog("=" * 70)

        return result

    # ========================================================
    # POST-TRAITEMENT COMMUN — étapes 5→9
    # ========================================================
    async def _finalize_opportunities(
        self,
        groq_opportunities: list[dict[str, Any]],
        groq_response: dict[str, Any],
        start_total: float,
        extra_statistics: dict[str, Any] | None = None,
        sync_backend: bool = True,
        date_reference: datetime | None = None,
        real_evidence: bool = False,
    ) -> dict[str, Any]:
        """Post-traitement : normalisation, qualité, classification, scoring,
        déduplication, validation, sync backend (si sync_backend)."""

        vlog("=" * 70)
        vlog(f"🔍 _finalize : {len(groq_opportunities)} opportunités depuis Groq")
        vlog("=" * 70)

        # ────────────────────────────────────────────────────
        # 5 — NORMALISATION / QUALITÉ / CLASSIFICATION / SCORING
        # ────────────────────────────────────────────────────
        normalized: list[dict[str, Any]] = []
        stats_rejected = {
            "normalize": 0,
            "quality_filter": 0,
            "echeance_depassee": 0,
            "hors_madagascar": 0,
            "score_trop_bas": 0,
        }

        for idx, opportunity in enumerate(groq_opportunities, start=1):
            title_preview = str(opportunity.get("title", "?"))[:60]
            vlog(f"🔍 [{idx}/{len(groq_opportunities)}] '{title_preview}'")

            # ── ÉTAPE A : NORMALIZE ──
            cleaned = validation_service.normalize_opportunity(opportunity)
            if cleaned is None:
                stats_rejected["normalize"] += 1
                vlog(f"   ❌ [{idx}] REJETÉ par normalize", "warning")
                continue

            vlog(
                f"   ✅ [{idx}] normalize OK | score={cleaned.get('score')}, "
                f"conf={cleaned.get('confidence')}, domain={cleaned.get('domain')}"
            )

            # ── ÉTAPE B : QUALITY FILTER ──
            if not validation_service.quality_filter(cleaned):
                stats_rejected["quality_filter"] += 1
                vlog(f"   ❌ [{idx}] REJETÉ par quality_filter", "warning")
                continue

            vlog(f"   ✅ [{idx}] quality_filter OK")

            # ── ÉTAPE B2 : GARDE-FOUS DÉTERMINISTES ──
            if echeance_depassee(cleaned.get("deadline"), date_reference):
                stats_rejected["echeance_depassee"] += 1
                vlog(
                    f"   ❌ [{idx}] REJETÉ par garde-fou : échéance dépassée "
                    f"({cleaned.get('deadline')})",
                    "warning",
                )
                continue

            if VEILLE_EXIGER_MADAGASCAR and not mentionne_madagascar(cleaned):
                stats_rejected["hors_madagascar"] += 1
                vlog(
                    f"   ❌ [{idx}] REJETÉ par garde-fou : aucune mention de Madagascar",
                    "warning",
                )
                continue

            # ── ÉTAPE C : CLASSIFICATION + COUNTRY ──
            classification = dict(self.classification_service.classify(cleaned))
            # La confiance du classificateur porte sur le domaine, pas sur
            # la véracité de l'annonce. Ne pas écraser la confiance d'extraction.
            classification.pop("confidence", None)
            cleaned.update(classification)

            country_scope = self.classification_service.detect_country(cleaned)
            if country_scope == "Inconnu":
                organizer = str(cleaned.get("organizer", "")).lower()
                summary = str(cleaned.get("summary", "")).lower()
                title = str(cleaned.get("title", "")).lower()
                combined = f"{organizer} {summary} {title}"
                if any(k in combined for k in ("madagascar", "antananarivo", "malgache")):
                    country_scope = "Madagascar"
                else:
                    country_scope = "Madagascar"

            cleaned["country_scope"] = country_scope

            # ── ÉTAPE D : SCORING ──
            scoring_data, scoring_reference = cleaned, date_reference
            if real_evidence:
                # Le scoring historique compare des datetimes naïfs. Pour le
                # réel, conserver la vraie heure vérifiée dans le fuseau local ;
                # une date seule n'est pas une clôture à minuit.
                local_now = datetime.now(UTC).astimezone(MADAGASCAR).replace(tzinfo=None)
                scoring_reference = local_now.replace(hour=0, minute=0, second=0, microsecond=0)
                if cleaned.get("deadline_at"):
                    scoring_data = {**cleaned, "deadline": datetime.fromisoformat(cleaned["deadline_at"]).astimezone(MADAGASCAR).replace(tzinfo=None).isoformat()}
                    scoring_reference = local_now
            cleaned.update(self.scoring_service.score(scoring_data, date_reference=scoring_reference))

            try:
                final_score = int(cleaned.get("score", 0))
            except (TypeError, ValueError):
                final_score = 0

            vlog(
                f"   📊 [{idx}] Score final = {final_score} "
                f"(seuil MIN={MIN_SCORE_TO_REVIEW})"
            )

            if final_score < MIN_SCORE_TO_REVIEW:
                stats_rejected["score_trop_bas"] += 1
                vlog(
                    f"   ❌ [{idx}] REJETÉ par MIN_SCORE_TO_REVIEW "
                    f"({final_score} < {MIN_SCORE_TO_REVIEW})",
                    "warning",
                )
                continue

            # ── ÉTAPE E : STATUT ──
            try:
                final_confidence = float(cleaned.get("confidence", 0))
            except (TypeError, ValueError):
                final_confidence = 0.0

            if (
                final_score >= MIN_SCORE_VALIDATED
                and final_confidence >= MIN_CONFIDENCE_VALIDATED
            ):
                cleaned["status"] = "validated"
            else:
                cleaned["status"] = "to_review"

            cleaned["ai_provider"] = "groq"
            cleaned["is_actionable"] = True
            verification_time = (date_reference or datetime.now(UTC)).isoformat()
            cleaned["freshness_status"] = statut_fraicheur(
                cleaned.get("deadline"), date_reference
            )
            cleaned.setdefault("captured_at", verification_time)
            cleaned["last_verified_at"] = verification_time
            cleaned.setdefault("ai_summary", cleaned.get("summary"))
            cleaned.setdefault("ai_relevance", cleaned.get("reason"))
            cleaned.setdefault("ai_recommendation", cleaned.get("recommendation"))
            cleaned.setdefault("ai_points_to_verify", [])

            normalized.append(cleaned)
            vlog(f"   ✅ [{idx}] AJOUTÉ | score={final_score}, status={cleaned['status']}")

        vlog("=" * 70)
        vlog(f"📊 Résumé après normalisation : {len(normalized)}/{len(groq_opportunities)} conservés")
        vlog(
            f"📊 Rejets : normalize={stats_rejected['normalize']} | "
            f"quality_filter={stats_rejected['quality_filter']} | "
            f"échéance={stats_rejected['echeance_depassee']} | "
            f"hors_madagascar={stats_rejected['hors_madagascar']} | "
            f"score_bas={stats_rejected['score_trop_bas']}"
        )
        vlog("=" * 70)

        # ────────────────────────────────────────────────────
        # 6 — DÉDUPLICATION + TRI
        # ────────────────────────────────────────────────────
        before_dedup = len(normalized)
        normalized = validation_service.deduplicate(normalized)
        vlog(f"📊 Après déduplication : {len(normalized)}/{before_dedup}")

        normalized.sort(key=lambda item: int(item.get("score", 0)), reverse=True)

        # ────────────────────────────────────────────────────
        # 7 — VALIDATION FINALE (schéma Pydantic)
        # ────────────────────────────────────────────────────
        schema_valid: list[dict[str, Any]] = []
        for idx, opportunity in enumerate(normalized, start=1):
            validated = validation_service.validate_against_schema(opportunity)
            if validated is not None:
                schema_valid.append(validated)
            else:
                logger.warning(
                    f"   ❌ [{idx}] REJETÉ par validate_against_schema : "
                    f"'{str(opportunity.get('title', '?'))[:50]}'"
                )

        vlog(f"📊 Après validation schéma : {len(schema_valid)}/{len(normalized)}")

        # ────────────────────────────────────────────────────
        # 8 — HITL (validation humaine avant sync Backend)
        # ────────────────────────────────────────────────────
        review_id = None
        if sync_backend:
            vlog("⏳ Création review HITL (CDC : validation avant Backend)...")
            top_title = schema_valid[0].get("title", "N/A")[:60] if schema_valid else "N/A"
            review_id = create_review(
                agent_id="agent_m1_veille",
                data={"opportunities": schema_valid},
                summary=f"Veille M1 — {len(schema_valid)} opportunité(s) — {top_title}",
                criticity="medium",
            )
            vlog(f"   ✅ Review HITL créée : {review_id}")
        sync_result = {
            "enabled": base_sync.is_sync_enabled(),
            "sent": 0,
            "deferred": True,
            "review_id": review_id,
        }

        # ────────────────────────────────────────────────────
        # 9 — STATISTIQUES + RÉPONSE
        # ────────────────────────────────────────────────────
        madagascar_count = sum(
            1 for o in schema_valid if o.get("country_scope") == "Madagascar"
        )

        elapsed = time.perf_counter() - start_total

        vlog("=" * 70)
        vlog("🏁 M1 — FIN")
        vlog(f"🤖 Résultats Groq : {len(groq_opportunities)}")
        vlog(f"✅ Opportunités finales : {len(schema_valid)}")
        vlog(f"🇲🇬 Madagascar : {madagascar_count}")
        vlog(f"⏱️ Temps total : {elapsed:.3f}s")
        vlog("=" * 70)

        statistics = {
            "groq_results": len(groq_opportunities),
            "final": len(schema_valid),
            "madagascar": madagascar_count,
            "backend_sync": sync_result,
            "processing_time_seconds": round(elapsed, 3),
            "llm_opportunities": len(groq_opportunities),
            "final_opportunities": len(schema_valid),
            "rejected_normalize": stats_rejected["normalize"],
            "rejected_quality_filter": stats_rejected["quality_filter"],
            "rejected_deadline_expired": stats_rejected["echeance_depassee"],
            "rejected_outside_madagascar": stats_rejected["hors_madagascar"],
            "rejected_score_bas": stats_rejected["score_trop_bas"],
        }
        if extra_statistics:
            statistics.update(extra_statistics)

        result = {
            "opportunities": schema_valid[:20],
            "market_signals": groq_response.get("market_signals", []),
            "total": len(schema_valid),
            "status": "success" if schema_valid else "no_results",
            "ai_provider": "groq",
            "statistics": statistics,
            "notes": groq_response.get(
                "notes", "Analyse M1 effectuée avec veille.yaml."
            ),
        }
        if review_id:
            result["_review_id"] = review_id
            result["_review_status"] = "pending_review"
        return result

    # ========================================================
    # HELPER — réponse vide
    # ========================================================

    @staticmethod
    def _empty_response(
        status: str,
        notes: str,
        elapsed: float = 0.0,
        raw_count: int = 0,
        timings: dict[str, float] | None = None,
        technical_reason: str | None = None,
        collection_diagnostics: dict | None = None,
    ) -> dict[str, Any]:
        result = {
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
                **(timings or {}),
            },
            "notes": notes,
        }
        if technical_reason:
            result["technical_reason"] = technical_reason
        if collection_diagnostics is not None:
            result["collection_diagnostics"] = collection_diagnostics
            if status == "no_results" and any(d.get("status") in {"failed", "not_searched"}
                                               for d in collection_diagnostics.get("domain_coverage", [])):
                result["status"] = "partial"
                result["notes"] = "Collecte incomplète : certains sites n'ont pas pu être recherchés. Aucune absence globale d'opportunités ne peut être conclue."
        return result

    # ========================================================
    # SYNCHRONISATION BACKEND — APRÈS APPROBATION HITL
    # ========================================================

    async def synchroniser_backend(
        self,
        review_id: str,
        force: bool = False,
    ) -> dict[str, Any]:
        """
        Envoie les opportunités approuvées au Backend.
        Appelé après validation HITL de l'analyse M1.

        Args:
            review_id: ID de la review HITL (agent_m1_veille).
            force: relance même si déjà envoyé.
        """
        from app.services.backend_sync import review_sync

        vlog(f"🔄 [M1] synchroniser_backend — review={review_id}")
        review = review_sync.load_approved_review(
            review_id, agent_ids=("agent_m1_veille",)
        )
        opportunities = (review.get("data") or {}).get("opportunities", [])

        async def _envoyer() -> dict[str, Any]:
            return await sync_opportunities_to_backend(opportunities)

        result = await review_sync.sync_once(review_id, _envoyer, force=force)
        vlog(f"   ✅ [M1] synchroniser_backend terminé : {result}")
        return result

    # ========================================================
    # ALIAS
    # ========================================================

    async def rechercher(self, query: str) -> dict[str, Any]:
        return await self.analyser_opportunites(query)
