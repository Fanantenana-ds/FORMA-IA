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

import logging
import os
import time
from typing import Any, Dict, List, Optional

from app.orchestrator.base_orchestrator import BaseOrchestrator, _vlog as vlog
from app.services.formations import (
    AttestationGeneratorService,
    FormGeneratorService,
    KnowledgeBaseService,
    LevelAnalyzerService,
    PresenceAnalyzerService,
    ReportGeneratorService,
    SatisfactionAnalyzerService,
)
from app.services.formations.google_forms_service import GoogleFormsService
from app.services.hitl import get_review

logger = logging.getLogger(__name__)


# ============================================================
# ORCHESTRATEUR
# ============================================================
class FormationOrchestrator(BaseOrchestrator):
    """Orchestrateur du module M5 — Gestion des Formations."""

    _name = "FormationOrchestrator"

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

        # ---- Agent 7 — KnowledgeBaseService ----
        self.knowledge_base = self._safe_init(
            KnowledgeBaseService, "Agent 7 — KnowledgeBaseService (RAG)",
        )

        # ---- Bilan de démarrage ----
        self._log_startup_summary({
            "Agent 1 — FormGenerator":         self.form_generator,
            "Agent 2 — LevelAnalyzer":         self.level_analyzer,
            "Agent 3 — SatisfactionAnalyzer":  self.satisfaction_analyzer,
            "Agent 4 — PresenceAnalyzer":      self.presence_analyzer,
            "Agent 5 — AttestationGenerator":  self.attestation_generator,
            "Agent 6 — ReportGenerator":       self.report_generator,
            "Agent 7 — KnowledgeBase (RAG)":   self.knowledge_base,
        })

    # ========================================================
    # AGENT 1 — GÉNÉRATION DES FORMULAIRES
    # ========================================================

    async def generate_forms(self, session_info: dict[str, Any]) -> dict[str, Any]:
        """Génère les 4 formulaires Google Forms d'une session."""
        start = self._log_start(
            "generate_forms",
            **{"📋 Session": session_info.get("titre", "N/A"),
               "🏷️  Domaine": session_info.get("domaine", "N/A")},
        )
        self._check_agent(self.form_generator, "Agent 1 (FormGeneratorService)")

        try:
            # Agent 7 enrichit session_info["supports_resume"] si disponible
            # et si le champ n'a pas déjà été fourni par l'appelant.
            if self.knowledge_base and not session_info.get("supports_resume"):
                try:
                    contexte = await self.knowledge_base.get_formation_context(
                        formation_titre=session_info.get("titre", ""),
                        domaine=session_info.get("domaine", ""),
                        formation_code=session_info.get("formation_code"),
                    )
                    if contexte:
                        session_info = dict(session_info)  # copie pour ne pas muter l'original
                        session_info["supports_resume"] = contexte
                        vlog("   📚 [FormationOrchestrator] Contexte RAG injecté dans generate_forms")
                except Exception as exc:
                    logger.warning(f"⚠️ [FormationOrchestrator] RAG non disponible pour generate_forms : {exc}")

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
        session_info: dict[str, Any],
        participants: list[dict[str, Any]],
        corrige: dict[str, str],
    ) -> dict[str, Any]:
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
        session_info: dict[str, Any],
        responses: list[dict[str, Any]],
    ) -> dict[str, Any]:
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
        session_info: dict[str, Any],
        participants: list[dict[str, Any]],
        presences: list[dict[str, Any]],
    ) -> dict[str, Any]:
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
        session_data: dict[str, Any],
        eligible_participants: list[dict[str, Any]],
    ) -> dict[str, Any]:
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

    async def generate_report(self, session_data: dict[str, Any]) -> dict[str, Any]:
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

    async def index_documents(self, documents: dict[str, Any]) -> dict[str, Any]:
        """Agent 7 — Indexation RAG (à venir — V2)."""
        logger.warning(
            "⚠️  [FormationOrchestrator] index_documents() "
            "non encore implémenté (Agent 7 — V2)."
        )
        return {"success": False, "reason": "not implemented"}

    # ========================================================
    # AGENT 1b — CRÉER FORMULAIRES GOOGLE (après approbation HITL)
    # ========================================================

    async def creer_formulaires_google(
        self, review_id: str, session_title: str = ""
    ) -> dict[str, Any]:
        """Publie les 4 Google Forms réels après approbation HITL."""
        start = self._log_start("creer_formulaires_google", Review_ID=review_id)

        review = get_review(review_id)
        if not review:
            raise ValueError(f"Review '{review_id}' introuvable.")
        if review.get("status") != "approved":
            raise ValueError(
                f"Review '{review_id}' non approuvé "
                f"(statut actuel : {review.get('status')})."
            )
        if review.get("agent_id") != "agent_1_forms":
            raise ValueError(
                f"Review '{review_id}' ne correspond pas à agent_1_forms "
                f"(agent : {review.get('agent_id')})."
            )

        approved_data = review.get("data") or {}
        try:
            gfs = GoogleFormsService()
            result = await gfs.create_forms(
                approved_data=approved_data,
                session_title=session_title,
            )

            # Stocker les form_id dans la review pour les récupérer plus tard
            from app.services.hitl import patch_review
            form_ids = {
                key: info.get("form_id", "")
                for key, info in result.get("forms", {}).items()
                if isinstance(info, dict) and "form_id" in info
            }
            if form_ids:
                patch_review(review_id, {"google_form_ids": form_ids})
                vlog(f"💾 form_id stockés dans review {review_id} : {list(form_ids.keys())}")

            self._log_end(
                "creer_formulaires_google", start,
                **{"✅ Créés": result.get("total_created", 0)},
            )
            return result
        except Exception as e:
            self._log_error("creer_formulaires_google", start, e)
            raise


    # ========================================================
    # SYNC RÉPONSES GOOGLE FORMS
    # ========================================================

    async def sync_responses(
        self,
        review_id: str,
        sections: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Récupère les réponses des formulaires Google liés à une review.

        Lit les form_id stockés dans review["meta"]["google_form_ids"]
        (enregistrés lors de creer_formulaires_google), appelle l'API
        Google Forms pour chaque section demandée, et retourne les
        réponses structurées prêtes pour les agents 2, 3, 4.

        Args:
            review_id: ID de la review agent_1_forms (contient les form_id).
            sections:  Liste de sections à récupérer, ex: ["satisfaction", "test_avant"].
                       None → toutes les sections disponibles.

        Returns:
            {
                "review_id": ...,
                "sections": {
                    "inscription": {"form_id": ..., "responses": [...], "count": int},
                    "test_avant":  {...},
                    "test_apres":  {...},
                    "satisfaction":{...},
                },
                "total_responses": int,
            }
        """
        from app.services.hitl import get_review
        from app.services.formations.google_forms_service import GoogleFormsService

        start = self._log_start(
            "sync_responses",
            **{"🔍 Review": review_id, "📋 Sections": sections or "toutes"},
        )

        review = get_review(review_id)
        if not review:
            raise ValueError(f"Review '{review_id}' introuvable.")
        if review.get("agent_id") != "agent_1_forms":
            raise ValueError(
                f"Review '{review_id}' n'est pas une review agent_1_forms "
                f"(agent : {review.get('agent_id')})."
            )

        meta = review.get("meta") or {}
        form_ids: Dict[str, str] = meta.get("google_form_ids") or {}

        if not form_ids:
            raise ValueError(
                f"Aucun form_id trouvé dans la review '{review_id}'. "
                "Appelez d'abord POST /ia/formations/creer-formulaires-google."
            )

        # Filtrer les sections demandées
        if sections:
            form_ids = {k: v for k, v in form_ids.items() if k in sections}
            if not form_ids:
                raise ValueError(
                    f"Aucune section parmi {sections} trouvée dans la review."
                )

        vlog(f"📥 Récupération réponses pour {list(form_ids.keys())}")

        try:
            gfs = GoogleFormsService()
            fetched = await gfs.fetch_responses(form_ids)

            total = sum(v.get("count", 0) for v in fetched.values())
            self._log_end(
                "sync_responses", start,
                **{"📊 Total réponses": total},
            )
            return {
                "review_id": review_id,
                "sections": fetched,
                "total_responses": total,
            }
        except Exception as e:
            self._log_error("sync_responses", start, e)
            raise

    # ========================================================
    # SYNC BACKEND — Présences (après approbation HITL A4)
    # ========================================================

    async def synchroniser_presences(
        self,
        review_id: str,
        seance_id: str,
        force: bool = False,
    ) -> Dict[str, Any]:
        """
        Enregistre les présences validées côté Backend
        (POST /sessions/seances/{seance_id}/presences).

        Args:
            review_id: ID du review HITL approuvé (agent_4_presences).
            seance_id: UUID Backend de la séance.
            force: relance même si déjà envoyé.
        """
        from app.services.backend_sync import review_sync, formation_sync

        start = self._log_start(
            "synchroniser_presences",
            **{"🔍 Review": review_id, "🗓 Seance": seance_id},
        )

        review = review_sync.load_approved_review(
            review_id, agent_ids=("agent_4_presences",)
        )
        data = review.get("data") or {}
        presences = data.get("presences_brutes") or data.get("presences") or []

        async def _envoyer() -> Dict[str, Any]:
            return await formation_sync.sync_presences_to_backend(
                seance_id=seance_id,
                presences=presences,
                source="GOOGLE_FORMS",
            )

        result = await review_sync.sync_once(review_id, _envoyer, force=force)
        self._log_end("synchroniser_presences", start)
        return result

    # ========================================================
    # SYNC BACKEND — Attestations (après approbation HITL A5)
    # ========================================================

    async def synchroniser_attestations(
        self,
        review_id: str,
        session_id: str,
        force: bool = False,
    ) -> Dict[str, Any]:
        """
        Déclenche la création des attestations côté Backend
        (POST /documents/attestations/{session_id}).

        Args:
            review_id: ID du review HITL approuvé (agent_5_attestations).
            session_id: UUID Backend de la session.
            force: relance même si déjà envoyé.
        """
        from app.services.backend_sync import review_sync, formation_sync

        start = self._log_start(
            "synchroniser_attestations",
            **{"🔍 Review": review_id, "📋 Session": session_id},
        )

        review_sync.load_approved_review(
            review_id, agent_ids=("agent_5_attestations",)
        )

        async def _envoyer() -> Dict[str, Any]:
            return await formation_sync.sync_attestations_to_backend(session_id)

        result = await review_sync.sync_once(review_id, _envoyer, force=force)
        self._log_end("synchroniser_attestations", start)
        return result


# ============================================================
# SINGLETON — pour FastAPI Depends
# ============================================================

_orchestrator_instance: FormationOrchestrator | None = None


def get_formation_orchestrator() -> FormationOrchestrator:
    """Retourne une instance unique (singleton) de FormationOrchestrator."""
    global _orchestrator_instance
    if _orchestrator_instance is None:
        logger.info("🔧 Création du singleton FormationOrchestrator...")
        _orchestrator_instance = FormationOrchestrator()
    return _orchestrator_instance
