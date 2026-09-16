import os
import time
import logging
from datetime import datetime,timedelta
from typing import Dict, Any, Optional, List

from app.services.preparation import (
    BudgetCalculatorService,
    EDTGeneratorService,
)
from app.services.hitl import create_review, get_review

logger = logging.getLogger(__name__)

VERBOSE = os.getenv("VERBOSE_LOGS", "true").lower() == "true"


def vlog(msg: str, level: str = "info") -> None:
    if VERBOSE:
        getattr(logger, level)(msg)


# =============================================================================
# ORCHESTRATEUR
# =============================================================================

class PreparationOrchestrator:
    """
    Orchestrateur de la Préparation de Formation.

    Coordonne :
        - BudgetCalculatorService (Python pur)
        - EDTGeneratorService (LLM)
        - HITL (validation humaine)
    """

    def __init__(self):
        vlog("=" * 70)
        vlog("🚀 Initialisation de PreparationOrchestrator...")
        vlog("=" * 70)

        self.budget_calculator = self._safe_init(
            BudgetCalculatorService,
            "BudgetCalculatorService (Python pur)",
        )
        self.edt_generator = self._safe_init(
            EDTGeneratorService,
            "EDTGeneratorService (LLM)",
        )

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
            "BudgetCalculatorService": self.budget_calculator is not None,
            "EDTGeneratorService":     self.edt_generator is not None,
        }
        active = [k for k, v in services_status.items() if v]
        inactive = [k for k, v in services_status.items() if not v]

        vlog("=" * 70)
        vlog(f"📊 Bilan démarrage Préparation : {len(active)}/2 services actifs")
        for name in active:
            vlog(f"   ✅ {name}")
        for name in inactive:
            vlog(f"   ⏳ {name} (en attente)")
        vlog("=" * 70)
        vlog("✅ PreparationOrchestrator initialisé avec succès.")

    def _check_services(self) -> None:
        missing = []
        if not self.budget_calculator:
            missing.append("BudgetCalculatorService")
        if not self.edt_generator:
            missing.append("EDTGeneratorService")
        if missing:
            raise RuntimeError(
                f"❌ Services Préparation manquants : {', '.join(missing)}"
            )

    def _log_start(self, method: str, **kwargs) -> float:
        vlog("=" * 70)
        vlog(f"🎬 [PreparationOrchestrator] → {method}()")
        for k, v in kwargs.items():
            vlog(f"   {k} : {v}")
        vlog("=" * 70)
        return time.perf_counter()

    def _log_end(self, method: str, start: float, **counts) -> float:
        elapsed = round(time.perf_counter() - start, 2)
        vlog("=" * 70)
        vlog(f"✅ [PreparationOrchestrator] {method}() terminé en {elapsed}s")
        for k, v in counts.items():
            vlog(f"   {k} : {v}")
        vlog("=" * 70)
        return elapsed

    def _log_error(self, method: str, start: float, e: Exception) -> None:
        elapsed = round(time.perf_counter() - start, 2)
        logger.error("=" * 70)
        logger.error(f"❌ [PreparationOrchestrator] {method}() ÉCHEC ({elapsed}s)")
        logger.error(f"   💥 Erreur : {type(e).__name__} — {e}")
        logger.error("=" * 70)

    # =========================================================================
    # CALCUL BUDGET UNIQUEMENT
    # =========================================================================

    def calculer_budget(
        self,
        formateur_info: Dict[str, Any],
        salle_info: Dict[str, Any],
        nb_jours: int,
        nb_participants: int,
        options: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Calcule uniquement le budget prévisionnel."""
        options = options or {}
        start = self._log_start(
            "calculer_budget",
            **{
                "👤 Formateur": formateur_info.get("nom", "N/A"),
                "🏛️  Salle": salle_info.get("nom", "N/A"),
                "📅 Jours": nb_jours,
                "👥 Participants": nb_participants,
            },
        )

        if not self.budget_calculator:
            raise RuntimeError("❌ BudgetCalculatorService non disponible.")

        try:
            result = self.budget_calculator.calculer(
                formateur_info=formateur_info,
                salle_info=salle_info,
                nb_jours=nb_jours,
                nb_participants=nb_participants,
                inclure_logistique=options.get("inclure_logistique", True),
                inclure_administration=options.get("inclure_administration", True),
            )

            self._log_end(
                "calculer_budget", start,
                **{"💰 Total": f"{result['cout_total']:,} MGA"},
            )
            return result

        except Exception as e:
            self._log_error("calculer_budget", start, e)
            raise

    # =========================================================================
    # GÉNÉRATION EDT UNIQUEMENT
    # =========================================================================

    async def generer_edt(
        self,
        titre_formation: str,
        modules: List[Dict[str, Any]],
        dates: List[str],
        formateur: Optional[Dict[str, Any]] = None,
        salle: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Génère uniquement l'emploi du temps."""
        start = self._log_start(
            "generer_edt",
            **{
                "📋 Formation": titre_formation,
                "📅 Jours": len(dates),
                "📚 Modules": len(modules),
            },
        )

        if not self.edt_generator:
            raise RuntimeError("❌ EDTGeneratorService non disponible.")

        try:
            result = await self.edt_generator.generate(
                titre_formation=titre_formation,
                modules=modules,
                dates=dates,
                formateur=formateur,
                salle=salle,
            )

            self._log_end(
                "generer_edt", start,
                **{
                    "📅 Jours": len(result.get("jours", [])),
                    "🔖 Source": result.get("metadata", {}).get("source"),
                },
            )
            return result

        except Exception as e:
            self._log_error("generer_edt", start, e)
            raise

    # =========================================================================
    # GÉNÉRATION COMPLÈTE (Budget + EDT + HITL)
    # =========================================================================

    async def generate_complete(
        self,
        offre_data: Dict[str, Any],
        projet_info: Dict[str, Any],
        ressources: Dict[str, Any],
        options: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Génère la préparation complète (budget + EDT + HITL).

        Args:
            offre_data: Données de l'offre (M3).
            projet_info: Informations du projet (client, participants).
            ressources: {formateur, salle}.
            options: {date_debut, date_fin, ...}.

        Returns:
            Dict avec budget + edt + review_id HITL.
        """
        options = options or {}
        start = self._log_start(
            "generate_complete",
            **{
                "📋 Offre": offre_data.get("reference", "N/A"),
                "🏢 Client": projet_info.get("client", "N/A"),
                "👥 Participants": projet_info.get("nb_participants", 20),
            },
        )
        self._check_services()

        try:
            # ═══════════════════════════════════════════════════════════
            # ① BUDGET PRÉVISIONNEL
            # ═══════════════════════════════════════════════════════════
            vlog("")
            vlog("💰 [1/3] Calcul du budget prévisionnel...")

            formateur = ressources.get("formateur", {})
            salle = ressources.get("salle", {})
            nb_jours = offre_data.get("duree_jours", 2)
            nb_participants = projet_info.get("nb_participants", 20)

            budget = self.budget_calculator.calculer(
                formateur_info=formateur,
                salle_info=salle,
                nb_jours=nb_jours,
                nb_participants=nb_participants,
                inclure_logistique=options.get("inclure_logistique", True),
                inclure_administration=options.get("inclure_administration", True),
            )
            vlog(f"   ✅ Budget : {budget['cout_total']:,} MGA")

            # ═══════════════════════════════════════════════════════════
            # ② EDT
            # ═══════════════════════════════════════════════════════════
            vlog("")
            vlog("📅 [2/3] Génération de l'emploi du temps...")

            # Construire les dates
            date_debut = options.get("date_debut")
            date_fin = options.get("date_fin")

            if date_debut and date_fin:
                dates = self._build_dates(date_debut, date_fin)
            else:
                dates = [f"2026-10-{15 + i}" for i in range(nb_jours)]

            modules = offre_data.get("modules", [])
            if not modules:
                # Générer des modules génériques
                modules = [
                    {"titre": f"Module {i+1}", "duree": "3h"}
                    for i in range(min(4, nb_jours * 2))
                ]

            edt = await self.edt_generator.generate(
                titre_formation=offre_data.get("titre", "Formation"),
                modules=modules,
                dates=dates,
                formateur=formateur,
                salle=salle,
            )
            vlog(f"   ✅ EDT : {len(edt.get('jours', []))} jour(s)")

            # ═══════════════════════════════════════════════════════════
            # ③ HITL REVIEW
            # ═══════════════════════════════════════════════════════════
            vlog("")
            vlog("🔗 [3/3] Création du review HITL...")

            result = {
                "success": True,
                "projet_id": projet_info.get("id"),
                "offre_id": projet_info.get("offre_id"),
                "client_id": projet_info.get("client_id"),
                "budget": budget,
                "edt": edt,
                "metadata": {
                    "generated_at": datetime.now().isoformat(),
                    "agent_id": "agent_preparation",
                },
            }

            review_id = create_review(
                agent_id="agent_preparation",
                data=result,
                summary=(
                    f"Préparation formation — {offre_data.get('titre', 'N/A')[:60]} "
                    f"— Budget : {budget['cout_total']:,} MGA "
                    f"— à valider avant démarrage"
                ),
                criticity="critical",
            )
            result["_review_id"] = review_id
            result["_review_status"] = "pending_review"

            self._log_end(
                "generate_complete", start,
                **{
                    "💰 Budget": f"{budget['cout_total']:,} MGA",
                    "📅 EDT": f"{len(edt.get('jours', []))} jour(s)",
                    "⏳ Review": review_id,
                },
            )

            return result

        except Exception as e:
            self._log_error("generate_complete", start, e)
            raise

    # =========================================================================
    # RÉGÉNÉRATION
    # =========================================================================

    async def regenerate(
        self,
        review_id: str,
        feedback: str,
    ) -> Dict[str, Any]:
        """Régénère une préparation à partir d'un review rejeté."""
        start = self._log_start(
            "regenerate",
            **{"🔍 Review": review_id, "💬 Feedback": feedback[:100]},
        )

        review = get_review(review_id)
        if not review:
            raise ValueError(f"❌ Review '{review_id}' introuvable.")

        if review.get("status") != "rejected":
            raise ValueError(
                f"❌ Review '{review_id}' n'est pas rejeté "
                f"(status: {review.get('status')})."
            )

        old_data = review.get("data", {})
        # Récupérer les données originales si disponibles
        offre_data = old_data.get("offre_data", old_data.get("offre_technique", {}))
        projet_info = old_data.get("projet_info", {})
        ressources = old_data.get("ressources", {})
        options = old_data.get("options", {})
        options["feedback"] = feedback
        options["regenerated_from"] = review_id

        try:
            result = await self.generate_complete(
                offre_data=offre_data,
                projet_info=projet_info,
                ressources=ressources,
                options=options,
            )
            self._log_end(
                "regenerate", start,
                **{
                    "🔄 Ancien": review_id,
                    "🆕 Nouveau": result.get("_review_id"),
                },
            )
            return result
        except Exception as e:
            self._log_error("regenerate", start, e)
            raise

    # =========================================================================
    # HELPERS
    # =========================================================================

    @staticmethod
    def _build_dates(date_debut: str, date_fin: str) -> List[str]:
        """Construit la liste des dates entre date_debut et date_fin."""
        try:
            d1 = datetime.strptime(date_debut, "%Y-%m-%d")
            d2 = datetime.strptime(date_fin, "%Y-%m-%d")
            delta = (d2 - d1).days
            return [
                (d1 + timedelta(days=i)).strftime("%Y-%m-%d")
                for i in range(delta + 1)
            ]
        except Exception:
            return [date_debut]


# =============================================================================
# SINGLETON
# =============================================================================

_preparation_orchestrator_instance: Optional[PreparationOrchestrator] = None


def get_preparation_orchestrator() -> PreparationOrchestrator:
    """Retourne le singleton PreparationOrchestrator."""
    global _preparation_orchestrator_instance
    if _preparation_orchestrator_instance is None:
        logger.info("🔧 Création du singleton PreparationOrchestrator...")
        _preparation_orchestrator_instance = PreparationOrchestrator()
    return _preparation_orchestrator_instance