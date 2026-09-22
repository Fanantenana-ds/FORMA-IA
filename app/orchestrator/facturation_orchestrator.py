# app/orchestrator/facturation_orchestrator.py
# ============================================================
# ORCHESTRATEUR M7 — Facturation (relances)
# ============================================================
# 1. Lit la facture côté Backend (GET /factures/{id}).
# 2. Calcule (Python) le reste dû, les jours de retard, le niveau
#    d'escalade (1/2/3).
# 3. Fait rédiger la relance par l'Agent M7 (LLM + repli gabarit).
# 4. Crée un review HITL — AUCUNE relance n'est envoyée sans
#    validation humaine (criticité "critical" : contenu adressé à un
#    vrai client).
#
# ⚠️ Le Backend n'a pas de route pour stocker/envoyer une relance
#    (POST /factures/{id}/relance calcule et retourne un texte à la
#    volée, sans persistance ni envoi). Il n'y a donc pas de route
#    /synchroniser ici, contrairement à M3/Préparation — la relance
#    approuvée doit être transmise autrement pour l'instant (dépendance
#    Backend à discuter si un envoi automatique est voulu).
# ============================================================

import os
import time
import logging
from typing import Any, Dict, Optional

from app.services.facturation import RelanceGeneratorService
from app.services.backend_sync.facture_calculator_service import FactureCalculatorService
from app.services.backend_sync import facture_sync
from app.services.hitl import create_review

logger = logging.getLogger(__name__)

VERBOSE = os.getenv("VERBOSE_LOGS", "true").lower() == "true"


def vlog(msg: str, level: str = "info") -> None:
    if VERBOSE:
        getattr(logger, level)(msg)


# =============================================================================
# ORCHESTRATEUR
# =============================================================================

class FacturationOrchestrator:
    """Orchestrateur du module M7 — Facturation et relances."""

    def __init__(self):
        vlog("=" * 70)
        vlog("🚀 Initialisation de FacturationOrchestrator...")
        vlog("=" * 70)

        self.relance_generator = self._safe_init(
            RelanceGeneratorService, "Agent M7 — RelanceGeneratorService"
        )
        self.calculator = self._safe_init(
            FactureCalculatorService, "FactureCalculatorService"
        )

        self._log_startup_summary()

    # =========================================================================
    # HELPERS INTERNES
    # =========================================================================

    def _safe_init(self, service_cls, label: str):
        try:
            instance = service_cls()
            vlog(f"   ✅ {label} prêt")
            return instance
        except Exception as e:
            logger.error(f"   ❌ {label} indisponible : {type(e).__name__} — {e}")
            return None

    def _log_startup_summary(self) -> None:
        services_status = {
            "Agent M7 — RelanceGenerator": self.relance_generator is not None,
            "FactureCalculatorService":    self.calculator is not None,
        }
        active = [k for k, v in services_status.items() if v]
        inactive = [k for k, v in services_status.items() if not v]

        vlog("=" * 70)
        vlog(f"📊 Bilan démarrage : {len(active)}/2 services actifs")
        for name in active:
            vlog(f"   ✅ {name}")
        for name in inactive:
            vlog(f"   ⏳ {name} (en attente)")
        vlog("=" * 70)
        vlog("✅ FacturationOrchestrator initialisé avec succès.")

    def _log_start(self, method: str, **kwargs) -> float:
        vlog("=" * 70)
        vlog(f"🎬 [FacturationOrchestrator] → {method}()")
        for k, v in kwargs.items():
            vlog(f"   {k} : {v}")
        vlog("=" * 70)
        return time.perf_counter()

    def _log_end(self, method: str, start: float, **counts) -> float:
        elapsed = round(time.perf_counter() - start, 2)
        vlog("=" * 70)
        vlog(f"✅ [FacturationOrchestrator] {method}() terminé en {elapsed}s")
        for k, v in counts.items():
            vlog(f"   {k} : {v}")
        vlog("=" * 70)
        return elapsed

    def _log_error(self, method: str, start: float, e: Exception) -> None:
        elapsed = round(time.perf_counter() - start, 2)
        logger.error("=" * 70)
        logger.error(f"❌ [FacturationOrchestrator] {method}() ÉCHEC ({elapsed}s)")
        logger.error(f"   💥 Erreur : {type(e).__name__} — {e}")
        logger.error("=" * 70)

    # =========================================================================
    # GÉNÉRER UNE RELANCE (Agent M7 + HITL)
    # =========================================================================

    async def generer_relance(self, facture_id: str) -> Dict[str, Any]:
        """
        Retourne :
          - {"success": True, "necessaire": False, "raison": ...} si aucune
            relance n'est nécessaire (facture soldée ou échéance non dépassée) ;
          - {"success": True, "necessaire": True, "objet", "texte", "niveau",
            "_review_id", "_review_status": "pending_review", ...} sinon.

        Lève ValueError si la facture est introuvable, RuntimeError si
        l'Agent M7 n'est pas disponible.
        """
        start = self._log_start("generer_relance", facture_id=facture_id)

        if not self.relance_generator or not self.calculator:
            raise RuntimeError("❌ Agent M7 (relances) non disponible.")

        try:
            facture = await facture_sync.fetch_facture(facture_id)
            if facture is None:
                raise ValueError(f"Facture introuvable côté Backend : {facture_id}")

            reste = self.calculator.calculer_reste_du(facture)
            if reste <= 0:
                self._log_end("generer_relance", start, Résultat="déjà soldée")
                return {
                    "success": True,
                    "necessaire": False,
                    "raison": "Facture déjà soldée (aucun montant restant dû).",
                    "facture_id": facture_id,
                }

            jours_retard = self.relance_generator.calculer_jours_retard(
                facture.get("date_echeance")
            )
            niveau = self.relance_generator.calculer_niveau(jours_retard)

            if niveau is None:
                self._log_end("generer_relance", start, Résultat="échéance non dépassée")
                return {
                    "success": True,
                    "necessaire": False,
                    "raison": "Échéance non dépassée : aucune relance nécessaire.",
                    "facture_id": facture_id,
                    "jours_retard": jours_retard,
                }

            facts = {
                "numero": facture.get("numero"),
                "client": facture.get("client"),
                "montant_restant_du": reste,
                "devise": "MGA",
                "date_echeance": str(facture.get("date_echeance") or ""),
                "jours_retard": jours_retard,
                "niveau": niveau,
            }

            contenu = await self.relance_generator.generate(facts)

            review_id = create_review(
                agent_id="agent_m7_relance",
                data={**contenu, "facture_id": facture_id},
                summary=(
                    f"Relance niveau {niveau} — Facture {facts['numero']} — "
                    f"{facts['montant_restant_du']} {facts['devise']}, "
                    f"{jours_retard}j de retard"
                ),
                criticity="critical",
            )

            result = {
                "success": True,
                "necessaire": True,
                "facture_id": facture_id,
                **contenu,
                "_review_id": review_id,
                "_review_status": "pending_review",
            }

            self._log_end(
                "generer_relance", start,
                Niveau=niveau, Retard=f"{jours_retard}j", Review=review_id,
            )
            return result

        except (ValueError, RuntimeError):
            raise
        except Exception as e:
            self._log_error("generer_relance", start, e)
            raise


# =============================================================================
# SINGLETON — pour FastAPI Depends
# =============================================================================

_facturation_orchestrator_instance: Optional[FacturationOrchestrator] = None


def get_facturation_orchestrator() -> FacturationOrchestrator:
    """
    Retourne une instance unique (singleton) de FacturationOrchestrator.

    Utilisable comme dépendance FastAPI :
        orchestrator: FacturationOrchestrator = Depends(get_facturation_orchestrator)
    """
    global _facturation_orchestrator_instance
    if _facturation_orchestrator_instance is None:
        logger.info("🔧 Création du singleton FacturationOrchestrator...")
        _facturation_orchestrator_instance = FacturationOrchestrator()
    return _facturation_orchestrator_instance
