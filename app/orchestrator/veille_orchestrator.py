import io
import logging
import os
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

import PyPDF2

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
from app.services.backend_sync.opportunity_sync import (
    sync_new_opportunities_to_backend,
    sync_opportunities_to_backend,
)
from app.services.backend_sync import base_sync

logger = logging.getLogger(__name__)

VERBOSE = os.getenv("VERBOSE_LOGS", "true").lower() == "true"


def vlog(msg: str, level: str = "info") -> None:
    """Log verbeux — contrôlé par VERBOSE_LOGS."""
    if VERBOSE:
        getattr(logger, level)(msg)


# ============================================================
# SEUILS — PERMISSIFS
# ============================================================
MIN_SCORE_VALIDATED = int(os.getenv("MIN_SCORE_VALIDATED", "15"))
MIN_SCORE_TO_REVIEW = int(os.getenv("MIN_SCORE_TO_REVIEW", "5"))
MIN_CONFIDENCE_VALIDATED = float(os.getenv("MIN_CONFIDENCE_VALIDATED", "0.10"))
MAX_RESULTS_AI = int(os.getenv("MAX_RESULTS_AI", "8"))
MAX_FALLBACK_BATCHES = int(os.getenv("MAX_FALLBACK_BATCHES", "2"))


# =============================================================================
# ORCHESTRATEUR
# =============================================================================

class VeilleOrchestrator:
    """Coordonne le pipeline M1 sans porter lui-même de logique métier."""

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

        self._log_startup_summary()

    # =========================================================================
    # HELPERS INTERNES
    # =========================================================================

    def _safe_init(self, cls, label: str):
        try:
            instance = cls()
            vlog(f"   ✅ {label} prêt")
            return instance
        except Exception as e:
            logger.error(f"   ❌ {label} indisponible : {type(e).__name__} — {e}")
            return None

    def _log_startup_summary(self) -> None:
        services_status = {
            "TavilyService":         self.tavily_service is not None,
            "LLMAnalysisService":    self.llm_service is not None,
            "ClassificationService": self.classification_service is not None,
            "ScoringService":        self.scoring_service is not None,
        }
        active = [k for k, v in services_status.items() if v]
        inactive = [k for k, v in services_status.items() if not v]

        vlog("=" * 70)
        vlog(f"📊 Bilan démarrage M1 : {len(active)}/4 services actifs")
        for name in active:
            vlog(f"   ✅ {name}")
        for name in inactive:
            vlog(f"   ⏳ {name} (en attente)")
        vlog("=" * 70)
        vlog("✅ VeilleOrchestrator initialisé avec succès.")

    # ========================================================
    # ENTRÉE 1 — RECHERCHE WEB
    # ========================================================

    async def analyser_opportunites(
        self, query: str, sync_backend: bool = True, categorie: str = "manuel"
    ) -> Dict[str, Any]:
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
        raw_results = await self.tavily_service.search(query, categorie=categorie)

        if not raw_results:
            return self._empty_response(
                status="no_results",
                notes="Aucun résultat Tavily.",
                elapsed=time.perf_counter() - start_total,
            )
        vlog(f"   ✅ {len(raw_results)} résultats bruts")

        # ── 2. CLASSEMENT (préfiltre) ──
        vlog("🏆 [2] Classement (préfiltre)...")
        ranked_results = rank_results(raw_results, query)

        if not ranked_results:
            return self._empty_response(
                status="no_results",
                notes="Aucun résultat après préfiltrage.",
                elapsed=time.perf_counter() - start_total,
                raw_count=len(raw_results),
            )
        vlog(f"   ✅ {len(ranked_results)} résultats après préfiltre")

        # ── 3/4. ANALYSE LLM PAR LOTS ──
        vlog(f"🤖 [3] Analyse LLM (max {MAX_FALLBACK_BATCHES} lot(s))...")
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

            vlog(
                f"🔁 Lot {batch_index + 1}/{MAX_FALLBACK_BATCHES} : "
                f"{len(batch)} source(s)"
            )

            batch_response = await self.llm_service.analyze(query, batch)
            filtered_results = batch

            if batch_response is None:
                logger.warning(
                    f"⚠️ Lot {batch_index + 1} : analyse Groq échouée, "
                    f"passage au lot suivant"
                )
                continue

            any_groq_success = True
            groq_response = batch_response
            last_notes = batch_response.get("notes")
            batch_opportunities = batch_response.get("opportunities", [])

            if batch_opportunities:
                vlog(
                    f"✅ Lot {batch_index + 1} : "
                    f"{len(batch_opportunities)} opportunité(s) — arrêt"
                )
                groq_opportunities = batch_opportunities
                break

            vlog(f"ℹ️ Lot {batch_index + 1} : aucune opportunité éligible")

        # ── CAS A : Aucun lot analysé ──
        if not any_groq_success:
            result = validation_service.fallback_response(filtered_results)
            elapsed = time.perf_counter() - start_total
            result["statistics"]["processing_time_seconds"] = round(elapsed, 3)
            vlog(f"🏁 M1 FALLBACK — FIN ({elapsed:.3f}s)")
            return result

        # ── CAS B : Tous les lots tentés, 0 opportunité ──
        if not groq_opportunities:
            elapsed = time.perf_counter() - start_total
            vlog(
                f"ℹ️ Aucune opportunité éligible après "
                f"{min(MAX_FALLBACK_BATCHES, batch_index + 1)} lot(s)"
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

        # ── 5→9. POST-TRAITEMENT COMMUN ──
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
            sync_backend=sync_backend,
        )

    # ========================================================
    # ENTRÉE 1 bis — DÉTECTION AUTOMATIQUE (sans requête saisie)
    # ========================================================

    async def detecter_automatiquement(
        self,
        queries: List[str],
        min_score: int = 40,
        limit: int = 20,
        sync_backend: bool = True,
    ) -> Dict[str, Any]:
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

        vlog("=" * 70)
        vlog(f"🤖 M1 DÉTECTION AUTOMATIQUE — DÉBUT ({len(queries)} requête(s))")
        vlog("=" * 70)

        par_requete: List[Dict[str, Any]] = []
        collectees: List[Dict[str, Any]] = []

        for query in queries:
            try:
                resultat = await self.analyser_opportunites(
                    query, sync_backend=False, categorie="auto"
                )
            except Exception as exc:
                logger.exception("❌ Détection auto — requête en échec : %s", query)
                par_requete.append({
                    "query": query, "status": "error",
                    "found": 0, "error": type(exc).__name__,
                })
                continue

            trouvees = [
                o for o in resultat.get("opportunities", []) if isinstance(o, dict)
            ]
            par_requete.append({
                "query": query,
                "status": resultat.get("status"),
                "found": len(trouvees),
            })
            for opportunite in trouvees:
                opportunite["detected_by_query"] = query
            collectees.extend(trouvees)

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

        ok = [r for r in par_requete if r["status"] in ("success", "no_results")]
        if not ok:
            statut = "degraded"
        elif len(ok) < len(par_requete):
            statut = "partial"
        else:
            statut = "success"

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
            "statistics": {
                "queries_run": len(queries),
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
        date_reference: Optional[datetime] = None,
    ) -> Dict[str, Any]:
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
    ) -> List[Dict[str, Any]]:
        """Découpe un texte long en plusieurs blocs 'source'."""
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
        reader = PyPDF2.PdfReader(io.BytesIO(pdf_bytes))
        pages = []
        for page in reader.pages:
            text = (page.extract_text() or "").strip()
            if text:
                pages.append(text)
        return "\n\n".join(pages)

    async def analyser_pdf(
        self, pdf_bytes: bytes, filename: str = "document.pdf"
    ) -> Dict[str, Any]:
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
        groq_opportunities: List[Dict[str, Any]],
        groq_response: Dict[str, Any],
        start_total: float,
        extra_statistics: Optional[Dict[str, Any]] = None,
        sync_backend: bool = True,
        date_reference: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """Post-traitement : normalisation, qualité, classification, scoring,
        déduplication, validation, sync backend (si sync_backend)."""

        vlog("=" * 70)
        vlog(f"🔍 _finalize : {len(groq_opportunities)} opportunités depuis Groq")
        vlog("=" * 70)

        # ────────────────────────────────────────────────────
        # 5 — NORMALISATION / QUALITÉ / CLASSIFICATION / SCORING
        # ────────────────────────────────────────────────────
        normalized: List[Dict[str, Any]] = []
        stats_rejected = {
            "normalize": 0,
            "quality_filter": 0,
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

            # ── ÉTAPE C : CLASSIFICATION + COUNTRY ──
            cleaned.update(self.classification_service.classify(cleaned))

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
            cleaned.update(self.scoring_service.score(cleaned, date_reference=date_reference))

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

            normalized.append(cleaned)
            vlog(f"   ✅ [{idx}] AJOUTÉ | score={final_score}, status={cleaned['status']}")

        vlog("=" * 70)
        vlog(f"📊 Résumé après normalisation : {len(normalized)}/{len(groq_opportunities)} conservés")
        vlog(
            f"📊 Rejets : normalize={stats_rejected['normalize']} | "
            f"quality_filter={stats_rejected['quality_filter']} | "
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
        schema_valid: List[Dict[str, Any]] = []
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
        # 8 — SYNC BACKEND
        # ────────────────────────────────────────────────────
        if sync_backend:
            vlog("🔄 Sync Backend...")
            sync_result = await sync_opportunities_to_backend(schema_valid)
            vlog(f"   ✅ Sync : {sync_result}")
        else:
            sync_result = {
                "enabled": base_sync.is_sync_enabled(),
                "sent": 0,
                "failed": 0,
                "deferred": True,
            }
            vlog("⏭️ Sync Backend différée (détection automatique)")

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
            "rejected_score_bas": stats_rejected["score_trop_bas"],
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
    # HELPER — réponse vide
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