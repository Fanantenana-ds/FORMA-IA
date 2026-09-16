import os
import time
import logging
from datetime import datetime
from typing import Dict, Any, Optional, List

from app.services.offres import (
    OffreTechniqueGeneratorService,
    OffreFinanciereGeneratorService,
    GrilleTarifaireService,
)
from app.services.hitl import create_review

logger = logging.getLogger(__name__)

VERBOSE = os.getenv("VERBOSE_LOGS", "true").lower() == "true"


def vlog(msg: str, level: str = "info") -> None:
    if VERBOSE:
        getattr(logger, level)(msg)


# =============================================================================
# ORCHESTRATEUR
# =============================================================================

class OffreOrchestrator:
    """
    Orchestrateur du module M3 — Offres techniques et financières.

    Coordonne les 2 agents + grille tarifaire.
    """

    def __init__(self):
        vlog("=" * 70)
        vlog("🚀 Initialisation de OffreOrchestrator...")
        vlog("=" * 70)

        # Agent M3-1
        self.offre_technique = self._safe_init(
            OffreTechniqueGeneratorService,
            "Agent M3-1 — OffreTechniqueGeneratorService",
        )

        # Agent M3-2
        self.offre_financiere = self._safe_init(
            OffreFinanciereGeneratorService,
            "Agent M3-2 — OffreFinanciereGeneratorService",
        )

        # Grille tarifaire (utilitaire)
        self.grille_tarifaire = self._safe_init(
            GrilleTarifaireService,
            "GrilleTarifaireService",
        )

        # Bilan
        self._log_startup_summary()

    # =========================================================================
    # HELPERS INTERNES
    # =========================================================================

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
        """Log un récapitulatif des services actifs."""
        services_status = {
            "Agent M3-1 — OffreTechnique":  self.offre_technique is not None,
            "Agent M3-2 — OffreFinanciere": self.offre_financiere is not None,
            "GrilleTarifaireService":       self.grille_tarifaire is not None,
        }
        active = [k for k, v in services_status.items() if v]
        inactive = [k for k, v in services_status.items() if not v]

        vlog("=" * 70)
        vlog(f"📊 Bilan démarrage : {len(active)}/3 services actifs")
        for name in active:
            vlog(f"   ✅ {name}")
        for name in inactive:
            vlog(f"   ⏳ {name} (en attente)")
        vlog("=" * 70)
        vlog("✅ OffreOrchestrator initialisé avec succès.")

    def _check_services(self) -> None:
        """Vérifie que tous les services sont disponibles."""
        missing = []
        if not self.offre_technique:
            missing.append("Agent M3-1 (OffreTechnique)")
        if not self.offre_financiere:
            missing.append("Agent M3-2 (OffreFinanciere)")
        if missing:
            raise RuntimeError(
                f"❌ Services M3 manquants : {', '.join(missing)}"
            )

    def _log_start(self, method: str, **kwargs) -> float:
        """Log de début uniforme."""
        vlog("=" * 70)
        vlog(f"🎬 [OffreOrchestrator] → {method}()")
        for k, v in kwargs.items():
            vlog(f"   {k} : {v}")
        vlog("=" * 70)
        return time.perf_counter()

    def _log_end(self, method: str, start: float, **counts) -> float:
        """Log de fin uniforme."""
        elapsed = round(time.perf_counter() - start, 2)
        vlog("=" * 70)
        vlog(f"✅ [OffreOrchestrator] {method}() terminé en {elapsed}s")
        for k, v in counts.items():
            vlog(f"   {k} : {v}")
        vlog("=" * 70)
        return elapsed

    def _log_error(self, method: str, start: float, e: Exception) -> None:
        """Log d'erreur uniforme."""
        elapsed = round(time.perf_counter() - start, 2)
        logger.error("=" * 70)
        logger.error(f"❌ [OffreOrchestrator] {method}() ÉCHEC ({elapsed}s)")
        logger.error(f"   💥 Erreur : {type(e).__name__} — {e}")
        logger.error("=" * 70)

    # =========================================================================
    # GÉNÉRATION COMPLÈTE (M3-1 + M3-2 + HITL)
    # =========================================================================

    async def generate_complete(
        self,
        tdr_data: Dict[str, Any],
        session_info: Dict[str, Any],
        options: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Génère une offre complète (technique + financière).

        Args:
            tdr_data: Données du TDR.
            session_info: Informations de session (client, formateur, etc.).
            options: Options pour l'offre financière.

        Returns:
            Dict avec offre_technique + offre_financière + HITL review.
        """
        options = options or {}
        start = self._log_start(
            "generate_complete",
            **{
                "📋 TDR": tdr_data.get("titre", "N/A"),
                "🏢 Client": session_info.get("client", "N/A"),
                "💰 Participants": options.get("nb_participants", 20),
            },
        )
        self._check_services()

        try:
            # ═══════════════════════════════════════════════════════════
            # ① ÉTAPE 1 : Offre technique (Agent M3-1)
            # ═══════════════════════════════════════════════════════════
            vlog("")
            vlog("📝 [1/3] Génération de l'offre technique...")
            offre_tech = await self.offre_technique.generate(
                tdr_data=tdr_data,
                session_info=session_info,
            )
            vlog(f"   ✅ Offre technique générée : {offre_tech.get('reference')}")

            # ═══════════════════════════════════════════════════════════
            # ② ÉTAPE 2 : Offre financière (Agent M3-2)
            # ═══════════════════════════════════════════════════════════
            vlog("")
            vlog("💰 [2/3] Génération de l'offre financière...")
            offre_fin = await self.offre_financiere.generate(
                offre_technique=offre_tech,
                options=options,
            )
            vlog(f"   ✅ Offre financière générée : {offre_fin.get('reference')}")

            # ═══════════════════════════════════════════════════════════
            # ③ ÉTAPE 3 : Combiner + HITL global
            # ═══════════════════════════════════════════════════════════
            vlog("")
            vlog("🔗 [3/3] Fusion + création du review HITL global...")

            # Récupérer les review_id individuels
            review_tech = offre_tech.get("_review_id")
            review_fin = offre_fin.get("_review_id")

            # Construire le résultat combiné
            result = {
                "success": True,
                "tdr_id": tdr_data.get("id"),
                "client_id": session_info.get("client_id"),
                "session_id": session_info.get("id"),

                # Résultats des agents
                "offre_technique": offre_tech,
                "offre_financiere": offre_fin,

                # Résumé financier (pour affichage rapide)
                "resume_financier": {
                    "sous_total_ht": offre_fin.get("recapitulatif", {}).get("sous_total_ht"),
                    "total_ttc": offre_fin.get("recapitulatif", {}).get("total_ttc"),
                    "net_a_payer": offre_fin.get("recapitulatif", {}).get("net_a_payer"),
                    "devise": offre_fin.get("devise", "MGA"),
                },

                # Références croisées (reviews individuels)
                "reviews_individuels": {
                    "technique": review_tech,
                    "financiere": review_fin,
                },

                # Métadonnées
                "metadata": {
                    "generated_at": datetime.now().isoformat(),
                    "agent_ids": ["agent_m3_technique", "agent_m3_financiere"],
                },
            }

            # Créer un review HITL global
            review_id_global = create_review(
                agent_id="agent_m3_complete",
                data=result,
                summary=(
                    f"Offre complète M3 — {tdr_data.get('titre', 'N/A')[:60]} "
                    f"— Net : {result['resume_financier']['net_a_payer']:,} "
                    f"{result['resume_financier']['devise']}"
                ),
                criticity="critical",
            )
            result["_review_id"] = review_id_global
            result["_review_status"] = "pending_review"

            # Log final
            self._log_end(
                "generate_complete", start,
                **{
                    "📄 Référence TECH": offre_tech.get("reference"),
                    "💰 Référence FIN": offre_fin.get("reference"),
                    "💵 Net à payer": f"{result['resume_financier']['net_a_payer']:,} MGA",
                    "⏳ Review HITL": review_id_global,
                },
            )

            return result

        except Exception as e:
            self._log_error("generate_complete", start, e)
            raise

    # =========================================================================
    # GÉNÉRATION TECHNIQUE UNIQUEMENT (Agent M3-1)
    # =========================================================================

    async def generate_technique(
        self,
        tdr_data: Dict[str, Any],
        session_info: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Génère uniquement l'offre technique."""
        start = self._log_start(
            "generate_technique",
            **{"📋 TDR": tdr_data.get("titre", "N/A")},
        )

        if not self.offre_technique:
            raise RuntimeError("❌ Agent M3-1 non disponible.")

        try:
            result = await self.offre_technique.generate(
                tdr_data=tdr_data,
                session_info=session_info,
            )
            self._log_end(
                "generate_technique", start,
                **{
                    "📄 Référence": result.get("reference"),
                    "⏳ Review": result.get("_review_id"),
                },
            )
            return result
        except Exception as e:
            self._log_error("generate_technique", start, e)
            raise

    # =========================================================================
    # GÉNÉRATION FINANCIÈRE UNIQUEMENT (Agent M3-2)
    # =========================================================================

    async def generate_financiere(
        self,
        offre_technique: Dict[str, Any],
        options: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Génère uniquement l'offre financière."""
        start = self._log_start(
            "generate_financiere",
            **{"📋 Offre TECH": offre_technique.get("reference", "N/A")},
        )

        if not self.offre_financiere:
            raise RuntimeError("❌ Agent M3-2 non disponible.")

        try:
            result = await self.offre_financiere.generate(
                offre_technique=offre_technique,
                options=options,
            )
            self._log_end(
                "generate_financiere", start,
                **{
                    "💰 Référence": result.get("reference"),
                    "💵 Net": f"{result.get('recapitulatif', {}).get('net_a_payer', 0):,} MGA",
                    "⏳ Review": result.get("_review_id"),
                },
            )
            return result
        except Exception as e:
            self._log_error("generate_financiere", start, e)
            raise

    # =========================================================================
    # RÉGÉNÉRATION AVEC FEEDBACK
    # =========================================================================

    async def regenerate(
        self,
        review_id: str,
        feedback: str,
    ) -> Dict[str, Any]:
        """
        Régénère une offre à partir d'un review rejeté.

        Args:
            review_id: ID du review rejeté.
            feedback: Feedback humain.

        Returns:
            Nouvelle offre + nouveau review.
        """
        from app.services.hitl import get_review

        start = self._log_start(
            "regenerate",
            **{"🔍 Review ID": review_id, "💬 Feedback": feedback[:100]},
        )

        # Récupérer le review rejeté
        review = get_review(review_id)
        if not review:
            raise ValueError(f"❌ Review '{review_id}' introuvable.")

        if review.get("status") != "rejected":
            raise ValueError(
                f"❌ Review '{review_id}' n'est pas rejeté "
                f"(status actuel : {review.get('status')})."
            )

        # Récupérer les données du review
        old_data = review.get("data", {})
        tdr_data = old_data.get("tdr_data", {})
        session_info = old_data.get("session_info", {})
        options = old_data.get("options", {})

        if not tdr_data:
            raise ValueError(
                "❌ Données du TDR manquantes dans le review. "
                "Impossible de régénérer."
            )

        # Ajouter le feedback aux options pour le LLM
        options["feedback"] = feedback
        options["regenerated_from"] = review_id

        # Régénérer
        try:
            result = await self.generate_complete(
                tdr_data=tdr_data,
                session_info=session_info,
                options=options,
            )
            self._log_end(
                "regenerate", start,
                **{
                    "🔄 Ancien review": review_id,
                    "🆕 Nouveau review": result.get("_review_id"),
                },
            )
            return result
        except Exception as e:
            self._log_error("regenerate", start, e)
            raise


# =============================================================================
# SINGLETON — pour FastAPI Depends
# =============================================================================

_offre_orchestrator_instance: Optional[OffreOrchestrator] = None


def get_offre_orchestrator() -> OffreOrchestrator:
    """
    Retourne une instance unique (singleton) de OffreOrchestrator.

    Utilisable comme dépendance FastAPI :
        orchestrator: OffreOrchestrator = Depends(get_offre_orchestrator)
    """
    global _offre_orchestrator_instance
    if _offre_orchestrator_instance is None:
        logger.info("🔧 Création du singleton OffreOrchestrator...")
        _offre_orchestrator_instance = OffreOrchestrator()
    return _offre_orchestrator_instance