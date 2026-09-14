"""
FormationOrchestrator — Module M5
==================================
Coordonne les 7 agents IA du module M5 (Gestion des Formations).

Agents :
    ✅ Agent 1 — FormGeneratorService
    ✅ Agent 2 — LevelAnalyzerService
    ✅ Agent 3 — SatisfactionAnalyzerService
    ✅ Agent 4 — PresenceAnalyzerService
    ✅ Agent 5 — AttestationGeneratorService
    ✅ Agent 6 — ReportGeneratorService
    ⏳ Agent 7 — KnowledgeBaseService (V2)

📝 LOGS : contrôle via .env → VERBOSE_LOGS=true|false (défaut: true en dev)
"""

import os
import time
import logging
from typing import Dict, Any, Optional, List

from app.services.formations import (
    FormGeneratorService,
    LevelAnalyzerService,
    SatisfactionAnalyzerService,
    PresenceAnalyzerService,
    AttestationGeneratorService,
    ReportGeneratorService,
)

logger = logging.getLogger(__name__)


# ============================================================
# CONFIG
# ============================================================
VERBOSE = os.getenv("VERBOSE_LOGS", "true").lower() == "true"


def vlog(msg: str, level: str = "info") -> None:
    """Log verbeux — contrôlé par VERBOSE_LOGS."""
    if not VERBOSE:
        return
    getattr(logger, level)(msg)


# ============================================================
# ORCHESTRATEUR
# ============================================================
class FormationOrchestrator:
    """Orchestrateur du module M5 — Gestion des Formations."""

    def __init__(self):
        vlog("=" * 70)
        vlog("🚀 Initialisation de FormationOrchestrator...")
        vlog("=" * 70)

        # ---- Agents 1 à 6 ----
        self.form_generator = self._safe_init(
            FormGeneratorService, "Agent 1 — FormGeneratorService",
        )
        self.level_analyzer = self._safe_init(
            LevelAnalyzerService, "Agent 2 — LevelAnalyzerService",
        )
        self.satisfaction_analyzer = self._safe_init(
            SatisfactionAnalyzerService, "Agent 3 — SatisfactionAnalyzerService",
        )
        self.presence_analyzer = self._safe_init(
            PresenceAnalyzerService, "Agent 4 — PresenceAnalyzerService",
        )
        self.attestation_generator = self._safe_init(
            AttestationGeneratorService, "Agent 5 — AttestationGeneratorService",
        )
        self.report_generator = self._safe_init(
            ReportGeneratorService, "Agent 6 — ReportGeneratorService",
        )

        # ---- Agent 7 (V2) ----
        self.knowledge_base = None

        # ---- Bilan de démarrage ----
        self._log_startup_summary()

    # ========================================================
    # HELPERS INTERNES
    # ========================================================

    def _safe_init(self, service_cls, label: str):
        """Initialise un service avec try/except + log uniforme."""
        try:
            instance = service_cls()
            vlog(f"   ✅ {label} prêt")
            return instance
        except Exception as e:
            logger.error(f"   ❌ {label} indisponible : {type(e).__name__} — {e}")
            return None

    def _log_startup_summary(self) -> None:
        """Log un récapitulatif des agents actifs / inactifs."""
        agents_status = {
            "Agent 1 — FormGenerator":         self.form_generator is not None,
            "Agent 2 — LevelAnalyzer":         self.level_analyzer is not None,
            "Agent 3 — SatisfactionAnalyzer":  self.satisfaction_analyzer is not None,
            "Agent 4 — PresenceAnalyzer":      self.presence_analyzer is not None,
            "Agent 5 — AttestationGenerator":  self.attestation_generator is not None,
            "Agent 6 — ReportGenerator":       self.report_generator is not None,
            "Agent 7 — KnowledgeBase (RAG)":   self.knowledge_base is not None,
        }
        active = [k for k, v in agents_status.items() if v]
        inactive = [k for k, v in agents_status.items() if not v]

        vlog("=" * 70)
        vlog(f"📊 Bilan démarrage : {len(active)}/7 agents actifs")
        for name in active:
            vlog(f"   ✅ {name}")
        for name in inactive:
            vlog(f"   ⏳ {name} (en attente)")
        vlog("=" * 70)
        vlog("✅ FormationOrchestrator initialisé avec succès.")

    # ========================================================
    # HELPERS — GESTION D'ERREUR UNIFORME
    # ========================================================

    def _check_agent(self, agent, name: str) -> None:
        """Vérifie qu'un agent est disponible, sinon RuntimeError."""
        if not agent:
            raise RuntimeError(f"❌ {name} non disponible.")

    def _log_start(self, method: str, **kwargs) -> float:
        """Log de début uniforme — retourne le timestamp start."""
        vlog("=" * 70)
        vlog(f"🎬 [FormationOrchestrator] → {method}()")
        for k, v in kwargs.items():
            vlog(f"   {k} : {v}")
        vlog("=" * 70)
        return time.perf_counter()

    def _log_end(self, method: str, start: float, **counts) -> float:
        """Log de fin uniforme — retourne l'élapsed en secondes."""
        elapsed = round(time.perf_counter() - start, 2)
        vlog("=" * 70)
        vlog(f"✅ [FormationOrchestrator] {method}() terminé en {elapsed}s")
        for k, v in counts.items():
            vlog(f"   {k} : {v}")
        vlog("=" * 70)
        return elapsed

    def _log_error(self, method: str, start: float, e: Exception) -> None:
        """Log d'erreur uniforme."""
        elapsed = round(time.perf_counter() - start, 2)
        logger.error("=" * 70)
        logger.error(f"❌ [FormationOrchestrator] {method}() ÉCHEC ({elapsed}s)")
        logger.error(f"   💥 Erreur : {type(e).__name__} — {e}")
        logger.error("=" * 70)

    # ========================================================
    # AGENT 1 — GÉNÉRATION DES FORMULAIRES
    # ========================================================

    async def generate_forms(self, session_info: Dict[str, Any]) -> Dict[str, Any]:
        """Génère les 4 formulaires Google Forms d'une session."""
        start = self._log_start(
            "generate_forms",
            **{"📋 Session": session_info.get("titre", "N/A"),
               "🏷️  Domaine": session_info.get("domaine", "N/A")},
        )
        self._check_agent(self.form_generator, "Agent 1 (FormGeneratorService)")

        try:
            result = await self.form_generator.generate(session_info)
            self._log_end(
                "generate_forms", start,
                **{"📊 Inscription": f"{len(result.get('inscription', {}).get('questions', []))} q",
                   "📊 Test AVANT": f"{len(result.get('test_avant', {}).get('questions', []))} q",
                   "📊 Test APRÈS": f"{len(result.get('test_apres', {}).get('questions', []))} q",
                   "📊 Satisfaction": f"{len(result.get('satisfaction', {}).get('questions', []))} q"},
            )
            return result
        except Exception as e:
            self._log_error("generate_forms", start, e)
            raise

    # ========================================================
    # AGENT 2 — ANALYSE DES NIVEAUX
    # ========================================================

    async def analyze_levels(
        self,
        session_info: Dict[str, Any],
        participants: List[Dict[str, Any]],
        corrige: Dict[str, str],
    ) -> Dict[str, Any]:
        """Agent 2 — Analyse les niveaux (avant/après)."""
        start = self._log_start(
            "analyze_levels",
            **{"📋 Session": session_info.get("titre", "N/A"),
               "👥 Participants": len(participants)},
        )
        self._check_agent(self.level_analyzer, "Agent 2 (LevelAnalyzerService)")

        try:
            result = await self.level_analyzer.analyze(session_info, participants, corrige)
            self._log_end(
                "analyze_levels", start,
                **{"📊 Progression": f"{result['statistiques']['progression_absolue']:+.1f} points",
                   "💡 Recommandations": len(result["recommandations"])},
            )
            return result
        except Exception as e:
            self._log_error("analyze_levels", start, e)
            raise

    # ========================================================
    # AGENT 3 — ANALYSE SATISFACTION
    # ========================================================

    async def analyze_satisfaction(
        self,
        session_info: Dict[str, Any],
        responses: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Agent 3 — Analyse la satisfaction des participants."""
        start = self._log_start(
            "analyze_satisfaction",
            **{"📋 Session": session_info.get("titre", "N/A"),
               "👥 Réponses": len(responses)},
        )
        self._check_agent(self.satisfaction_analyzer, "Agent 3 (SatisfactionAnalyzerService)")

        try:
            result = await self.satisfaction_analyzer.analyze(session_info, responses)
            self._log_end(
                "analyze_satisfaction", start,
                **{"📊 Note globale": f"{result['statistiques']['notes']['note_globale']}/5",
                   "💡 Recommandations": len(result["recommandations"])},
            )
            return result
        except Exception as e:
            self._log_error("analyze_satisfaction", start, e)
            raise

    # ========================================================
    # AGENT 4 — ANALYSE PRÉSENCES
    # ========================================================

    async def analyze_presences(
        self,
        session_info: Dict[str, Any],
        participants: List[Dict[str, Any]],
        presences: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Agent 4 — Analyse les présences (Python pur)."""
        start = self._log_start(
            "analyze_presences",
            **{"📋 Session": session_info.get("titre", "N/A"),
               "👥 Participants": len(participants),
               "📅 Présences": len(presences)},
        )
        self._check_agent(self.presence_analyzer, "Agent 4 (PresenceAnalyzerService)")

        try:
            result = self.presence_analyzer.analyze(session_info, participants, presences)
            self._log_end(
                "analyze_presences", start,
                **{"📊 Taux global": result["statistiques"]["taux_presence_global"],
                   "🔍 Anomalies": len(result["anomalies"]),
                   "✅ Éligibles attestation": len(result["eligibles_attestation"])},
            )
            return result
        except Exception as e:
            self._log_error("analyze_presences", start, e)
            raise

    # ========================================================
    # AGENT 5 — GÉNÉRATION DES ATTESTATIONS
    # ========================================================

    async def generate_attestations(
        self,
        session_data: Dict[str, Any],
        eligible_participants: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Agent 5 — Génère les attestations (JSON + PDF)."""
        start = self._log_start(
            "generate_attestations",
            **{"📋 Session": session_data.get("titre", "N/A"),
               "🏷️  Domaine": session_data.get("domaine", "N/A"),
               "👥 Participants éligibles": len(eligible_participants)},
        )
        self._check_agent(self.attestation_generator, "Agent 5 (AttestationGeneratorService)")

        if not eligible_participants:
            logger.warning("⚠️  Aucun participant éligible — attestations vides.")
            return {
                "success": True,
                "session_id": session_data.get("id"),
                "total_eligible": 0,
                "total_generated": 0,
                "total_failed": 0,
                "attestations": [],
                "failed_participants": [],
                "duration_seconds": 0.0,
            }

        try:
            result = await self.attestation_generator.generate_batch_with_pdf(
                session_data, eligible_participants
            )
            self._log_end(
                "generate_attestations", start,
                **{"📊 Générées": f"{result.get('total_generated', 0)}/{result.get('total_eligible', 0)}",
                   "❌ Échecs": result.get("total_failed", 0)},
            )
            return result
        except Exception as e:
            self._log_error("generate_attestations", start, e)
            raise

    # ========================================================
    # AGENT 6 — GÉNÉRATION DU RAPPORT FINAL
    # ========================================================

    async def generate_report(self, session_data: Dict[str, Any]) -> Dict[str, Any]:
        """Agent 6 — Génère le rapport final de formation."""
        start = self._log_start(
            "generate_report",
            **{"📋 Session": session_data.get("titre", "N/A"),
               "👥 Participants": session_data.get("total_inscrits", 0)},
        )
        self._check_agent(self.report_generator, "Agent 6 (ReportGeneratorService)")

        try:
            result = await self.report_generator.generate(session_data)
            self._log_end(
                "generate_report", start,
                **{"💡 Recommandations": len(result.get("recommandations", [])),
                   "📄 Source": result.get("metadata", {}).get("source")},
            )
            return result
        except Exception as e:
            self._log_error("generate_report", start, e)
            raise

    # ========================================================
    # AGENT 7 — INDEXATION RAG (V2)
    # ========================================================

    async def index_documents(self, documents: Dict[str, Any]) -> Dict[str, Any]:
        """Agent 7 — Indexation RAG (à venir — V2)."""
        logger.warning(
            "⚠️  [FormationOrchestrator] index_documents() "
            "non encore implémenté (Agent 7 — V2)."
        )
        raise NotImplementedError("Agent 7 (KnowledgeBase/RAG) à venir — V2.")


# ============================================================
# SINGLETON — pour FastAPI Depends
# ============================================================

_orchestrator_instance: Optional[FormationOrchestrator] = None


def get_formation_orchestrator() -> FormationOrchestrator:
    """Retourne une instance unique (singleton) de FormationOrchestrator."""
    global _orchestrator_instance
    if _orchestrator_instance is None:
        logger.info("🔧 Création du singleton FormationOrchestrator...")
        _orchestrator_instance = FormationOrchestrator()
    return _orchestrator_instance