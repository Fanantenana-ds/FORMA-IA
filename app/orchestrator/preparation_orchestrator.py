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
from app.services.backend_sync import preparation_sync, review_sync

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
                # Dates par défaut : à partir du 15/10/2026 (avant : f"2026-10-{15+i}",
                # ce qui donnait des dates invalides comme 2026-10-32 au-delà de 17 jours)
                debut = datetime(2026, 10, 15)
                dates = [
                    (debut + timedelta(days=i)).strftime("%Y-%m-%d")
                    for i in range(nb_jours)
                ]

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
                feedback=options.get("feedback"),
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
                # Données d'entrée : nécessaires à /regenerer (le review
                # rejeté est la seule source) et à la sync Backend.
                # Le feedback n'est pas conservé : chaque régénération
                # repart des entrées avec SON feedback.
                "_inputs": {
                    "offre_data": offre_data,
                    "projet_info": projet_info,
                    "ressources": ressources,
                    "options": {
                        k: v for k, v in options.items()
                        if k not in ("feedback", "regenerated_from")
                    },
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

        if review.get("agent_id") != "agent_preparation":
            raise ValueError(
                f"❌ Review '{review_id}' produit par "
                f"'{review.get('agent_id')}', pas par la Préparation."
            )

        # Données d'entrée mémorisées par generate_complete()
        old_data = review.get("data", {})
        inputs = old_data.get("_inputs")
        if not inputs:
            raise ValueError(
                f"❌ Review '{review_id}' sans données d'entrée mémorisées "
                f"(créé avant leur enregistrement) : relancez /generer-complet."
            )
        offre_data = inputs.get("offre_data") or {}
        projet_info = inputs.get("projet_info") or {}
        ressources = inputs.get("ressources") or {}
        options = dict(inputs.get("options") or {})
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
    # SYNCHRONISATION BACKEND (après approbation HITL)
    # =========================================================================

    async def synchroniser_backend(
        self,
        review_id: str,
        formateur_id: Optional[str] = None,
        force: bool = False,
    ) -> Dict[str, Any]:
        """
        Enregistre la préparation APPROUVÉE côté Backend : une session et
        une séance par jour d'EDT (le budget n'a pas de route Backend :
        il n'est pas persisté, voir preparation_sync).

        Garde-fous : review approuvé uniquement (agent_preparation), un seul
        envoi par review (sauf force=True : crée alors une NOUVELLE session).

        Args:
            review_id: review de la préparation.
            formateur_id: UUID d'un utilisateur Backend (facultatif).

        Raises:
            ValueError: review introuvable / non approuvé / d'un autre agent.
        """
        start = self._log_start(
            "synchroniser_backend",
            **{"🔍 Review": review_id, "🔁 Force": force},
        )

        review = review_sync.load_approved_review(
            review_id, agent_ids=("agent_preparation",)
        )
        data = review.get("data") or {}
        inputs = data.get("_inputs") or {}

        async def _envoyer() -> Dict[str, Any]:
            return await preparation_sync.sync_preparation_to_backend(
                edt=data.get("edt") or {},
                projet_info=inputs.get("projet_info"),
                budget=data.get("budget"),
                formateur_id=formateur_id,
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