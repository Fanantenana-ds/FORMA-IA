import os
import time
import logging
from datetime import datetime
from typing import Dict, Any, Optional

from app.services.tdr.tdr_service import TDRService
from app.services.tdr.tdr_document_generator import TDRDocumentGenerator
from app.services.backend_sync.tdr_sync import sync_tdr_to_backend
from app.services.backend_sync import review_sync
from app.services.hitl import create_review

logger = logging.getLogger(__name__)

VERBOSE = os.getenv("VERBOSE_LOGS", "true").lower() == "true"


def vlog(msg: str, level: str = "info") -> None:
    """Log verbeux — contrôlé par VERBOSE_LOGS."""
    if VERBOSE:
        getattr(logger, level)(msg)


# =============================================================================
# ORCHESTRATEUR
# =============================================================================

class TdrOrchestrator:
    """
    Orchestrateur M2 — coordonne service IA + générateur + sync.

    Pipeline :
        brief → TDR JSON → Word → PDF → Sync Backend
    """

    def __init__(self):
        vlog("=" * 70)
        vlog("🚀 Initialisation de TdrOrchestrator...")
        vlog("=" * 70)

        # Service IA (génération du contenu TDR)
        self.tdr_service = self._safe_init(
            TDRService,
            "TDRService (Agent IA)",
        )

        # Générateur documents (Word + PDF)
        self.document_generator = self._safe_init(
            TDRDocumentGenerator,
            "TDRDocumentGenerator (Word + PDF)",
        )

        # Bilan démarrage
        self._log_startup_summary()

    # =========================================================================
    # HELPERS INTERNES
    # =========================================================================

    def _safe_init(self, cls, label: str):
        """Initialise un service avec try/except + log uniforme."""
        try:
            instance = cls()
            vlog(f"   ✅ {label} prêt")
            return instance
        except Exception as e:
            logger.error(f"   ❌ {label} indisponible : {type(e).__name__} — {e}")
            return None

    def _log_startup_summary(self) -> None:
        """Log un récapitulatif des services actifs."""
        services_status = {
            "TDRService (IA)":              self.tdr_service is not None,
            "TDRDocumentGenerator":         self.document_generator is not None,
        }
        active = [k for k, v in services_status.items() if v]
        inactive = [k for k, v in services_status.items() if not v]

        vlog("=" * 70)
        vlog(f"📊 Bilan démarrage M2 : {len(active)}/2 services actifs")
        for name in active:
            vlog(f"   ✅ {name}")
        for name in inactive:
            vlog(f"   ⏳ {name} (en attente)")
        vlog("=" * 70)
        vlog("✅ TdrOrchestrator initialisé avec succès.")

    def _check_services(self) -> None:
        """Vérifie que tous les services sont disponibles."""
        missing = []
        if not self.tdr_service:
            missing.append("TDRService")
        if not self.document_generator:
            missing.append("TDRDocumentGenerator")
        if missing:
            raise RuntimeError(
                f"❌ Services M2 manquants : {', '.join(missing)}"
            )

    def _log_start(self, method: str, **kwargs) -> float:
        """Log de début uniforme — retourne le timestamp start."""
        vlog("=" * 70)
        vlog(f"🎬 [TdrOrchestrator] → {method}()")
        for k, v in kwargs.items():
            vlog(f"   {k} : {v}")
        vlog("=" * 70)
        return time.perf_counter()

    def _log_end(self, method: str, start: float, **counts) -> float:
        """Log de fin uniforme — retourne l'élapsed en secondes."""
        elapsed = round(time.perf_counter() - start, 2)
        vlog("=" * 70)
        vlog(f"✅ [TdrOrchestrator] {method}() terminé en {elapsed}s")
        for k, v in counts.items():
            vlog(f"   {k} : {v}")
        vlog("=" * 70)
        return elapsed

    def _log_error(self, method: str, start: float, e: Exception) -> None:
        """Log d'erreur uniforme."""
        elapsed = round(time.perf_counter() - start, 2)
        logger.error("=" * 70)
        logger.error(f"❌ [TdrOrchestrator] {method}() ÉCHEC ({elapsed}s)")
        logger.error(f"   💥 Erreur : {type(e).__name__} — {e}")
        logger.error("=" * 70)

    # =========================================================================
    # GÉNÉRATION COMPLÈTE
    # =========================================================================

    async def generate(self, brief: Dict[str, Any]) -> Dict[str, Any]:
        """
        Pipeline complet : brief → TDR JSON → Word → PDF → review HITL.

        Correction 1a/1b (2026-09-25) : le TDR n'est PLUS envoyé au Backend
        directement ici (contrairement à l'ancien comportement). Un review
        HITL (agent_m2_tdr) est créé — la synchronisation Backend n'a lieu
        qu'après approbation humaine, via synchroniser_backend(), même
        mécanisme que M3 (offre_orchestrator.py).

        Args:
            brief: Informations du brief client (client, objectifs, etc.).

        Returns:
            {
                "success": bool,
                "data": Dict (contenu TDR),
                "files": {"docx": str, "pdf": str},
                "_inputs": {"brief": Dict},
                "_review_id": str,
                "_review_status": "pending_review",
                "duration_seconds": float,
                "error": Optional[str],
            }
        """
        start = self._log_start(
            "generate",
            **{
                "📋 Client": brief.get("client", "N/A"),
                "🎯 Objectifs": str(brief.get("objectifs", "N/A"))[:80],
                "👥 Public cible": brief.get("public_cible", "N/A"),
            },
        )
        self._check_services()

        try:
            # ═══════════════════════════════════════════════════════════
            # ① ÉTAPE 1 : Génération IA (TDR JSON)
            # ═══════════════════════════════════════════════════════════
            vlog("")
            vlog("📝 [1/3] Génération du contenu TDR (Agent IA)...")

            tdr_content = await self.tdr_service.generate(brief)

            if not tdr_content:
                raise ValueError("❌ TDRService : réponse vide ou None.")

            vlog(f"   ✅ TDR JSON généré ({len(str(tdr_content))} chars)")

            # ═══════════════════════════════════════════════════════════
            # ② ÉTAPE 2 : Génération documents (Word + PDF)
            # ═══════════════════════════════════════════════════════════
            vlog("")
            vlog("📄 [2/3] Génération des documents Word + PDF...")

            docx_filename, pdf_filename = self.document_generator.generate(
                tdr_content=tdr_content,
                client=brief.get("client", "Client"),
            )

            vlog(f"   ✅ Word : {docx_filename}")
            vlog(f"   ✅ PDF  : {pdf_filename}")

            # ═══════════════════════════════════════════════════════════
            # ③ ÉTAPE 3 : Review HITL (AUCUN envoi Backend ici)
            # ═══════════════════════════════════════════════════════════
            vlog("")
            vlog("⏳ [3/3] Création du review HITL (CDC : validation humaine avant Backend)...")

            result = {
                "success": True,
                "data": tdr_content,
                "files": {
                    "docx": docx_filename,
                    "pdf": pdf_filename,
                },
                "_inputs": {"brief": brief},
                "error": None,
            }

            review_id = create_review(
                agent_id="agent_m2_tdr",
                data=result,
                summary=f"TDR — {brief.get('client', 'N/A')} — {tdr_content.get('titre', 'N/A')[:60]}",
                criticity="critical",
            )
            result["_review_id"] = review_id
            result["_review_status"] = "pending_review"

            # ═══════════════════════════════════════════════════════════
            # ④ RÉSULTAT
            # ═══════════════════════════════════════════════════════════
            elapsed = self._log_end(
                "generate", start,
                **{
                    "📄 Word": docx_filename,
                    "📄 PDF": pdf_filename,
                    "⏳ Review HITL": review_id,
                },
            )

            result["duration_seconds"] = elapsed
            return result

        except Exception as e:
            self._log_error("generate", start, e)
            return {
                "success": False,
                "error": f"{type(e).__name__} : {e}",
                "data": None,
                "files": None,
                "backend_sync": None,
                "duration_seconds": round(time.perf_counter() - start, 2),
            }

    # =========================================================================
    # SYNCHRONISATION BACKEND — APRÈS APPROBATION HITL (correction 1b)
    # =========================================================================

    async def synchroniser_backend(
        self,
        review_id: str,
        opportunite_id: Optional[str] = None,
        force: bool = False,
    ) -> Dict[str, Any]:
        """
        Envoie le TDR APPROUVÉ au Backend. Même mécanisme que M3
        (OffreOrchestrator.synchroniser_backend) : garde-fou via
        review_sync.load_approved_review (review approuvé + bon agent
        uniquement), un seul envoi par review (sauf force=True).

        Args:
            review_id: review du TDR (agent_m2_tdr).
            opportunite_id: UUID de l'opportunité Backend liée. À défaut,
                lu dans le brief mémorisé (_inputs.brief.opportunite_id).

        Raises:
            ValueError: review introuvable / non approuvé / d'un autre agent.
        """
        start = self._log_start(
            "synchroniser_backend",
            **{"🔍 Review": review_id, "🔁 Force": force},
        )

        review = review_sync.load_approved_review(
            review_id, agent_ids=("agent_m2_tdr",)
        )
        data = review.get("data") or {}
        inputs = data.get("_inputs") or {}
        brief = inputs.get("brief") or {}
        files = data.get("files") or {}

        opportunite_id = opportunite_id or brief.get("opportunite_id")

        async def _envoyer() -> Dict[str, Any]:
            return await sync_tdr_to_backend(
                tdr_content=data.get("data") or {},
                docx_filename=files.get("docx"),
                pdf_filename=files.get("pdf"),
                opportunite_id=opportunite_id,
            )

        result = await review_sync.sync_once(review_id, _envoyer, force=force)
        self._log_end(
            "synchroniser_backend", start,
            **{
                "📤 Envoyé": (result["backend_sync"] or {}).get("sent"),
                "♻️  Déjà synchronisé": result["already_synced"],
            },
        )
        return result


# =============================================================================
# SINGLETON — pour FastAPI Depends
# =============================================================================

_tdr_orchestrator_instance: Optional[TdrOrchestrator] = None


def get_tdr_orchestrator() -> TdrOrchestrator:
    """
    Retourne une instance unique (singleton) de TdrOrchestrator.

    Utilisable comme dépendance FastAPI :
        orchestrator: TdrOrchestrator = Depends(get_tdr_orchestrator)
    """
    global _tdr_orchestrator_instance
    if _tdr_orchestrator_instance is None:
        logger.info("🔧 Création du singleton TdrOrchestrator...")
        _tdr_orchestrator_instance = TdrOrchestrator()
    return _tdr_orchestrator_instance