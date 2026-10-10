# app/orchestrator/base_orchestrator.py
# ============================================================
# Classe de base pour tous les orchestrateurs.
# Centralise : _safe_init, _log_startup_summary, _log_start,
#              _log_end, _log_error, _check_agent.
# ============================================================

import logging
import os
import time
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

_VERBOSE = os.getenv("VERBOSE_LOGS", "true").lower() == "true"


def _vlog(msg: str, level: str = "info") -> None:
    if _VERBOSE:
        getattr(logger, level)(msg)


class BaseOrchestrator:
    """
    Classe mère pour tous les orchestrateurs IA.

    Sous-classe minimale :
        class MonOrchestrator(BaseOrchestrator):
            _name = "MonOrchestrator"
    """

    _name: str = "Orchestrator"

    # ------------------------------------------------------------------
    # Initialisation des services
    # ------------------------------------------------------------------

    def _safe_init(self, service_cls, label: str):
        """Instancie service_cls() avec log uniforme; retourne None si échec."""
        try:
            instance = service_cls()
            _vlog(f"   ✅ {label} prêt")
            return instance
        except Exception as e:
            logger.error(f"   ❌ {label} indisponible : {type(e).__name__} — {e}")
            return None

    def _log_startup_summary(self, agents: dict[str, Any]) -> None:
        """
        Log un bilan de démarrage à partir d'un dict {label: instance_or_None}.

        Usage dans __init__ :
            self._log_startup_summary({
                "Agent 1 — FormGenerator": self.form_generator,
                "Agent 2 — Analyzer":      self.analyzer,
            })
        """
        total = len(agents)
        active = [k for k, v in agents.items() if v is not None]
        inactive = [k for k, v in agents.items() if v is None]

        _vlog("=" * 70)
        _vlog(f"📊 Bilan démarrage : {len(active)}/{total} agents actifs")
        for name in active:
            _vlog(f"   ✅ {name}")
        for name in inactive:
            _vlog(f"   ⏳ {name} (en attente)")
        _vlog("=" * 70)
        _vlog(f"✅ {self._name} initialisé avec succès.")

    # ------------------------------------------------------------------
    # Logs de début / fin de méthode
    # ------------------------------------------------------------------

    def _log_start(self, method: str, **kwargs) -> float:
        """Log de début uniforme — retourne le timestamp perf_counter."""
        _vlog("=" * 70)
        _vlog(f"🎬 [{self._name}] → {method}()")
        for k, v in kwargs.items():
            _vlog(f"   {k} : {v}")
        _vlog("=" * 70)
        return time.perf_counter()

    def _log_end(self, method: str, start: float, **counts) -> float:
        """Log de fin uniforme — retourne l'élapsed en secondes."""
        elapsed = round(time.perf_counter() - start, 2)
        _vlog("=" * 70)
        _vlog(f"✅ [{self._name}] {method}() terminé en {elapsed}s")
        for k, v in counts.items():
            _vlog(f"   {k} : {v}")
        _vlog("=" * 70)
        return elapsed

    def _log_error(self, method: str, start: float, e: Exception) -> None:
        """Log d'erreur uniforme."""
        elapsed = round(time.perf_counter() - start, 2)
        logger.error("=" * 70)
        logger.error(f"❌ [{self._name}] {method}() ÉCHEC ({elapsed}s)")
        logger.error(f"   💥 Erreur : {type(e).__name__} — {e}")
        logger.error("=" * 70)

    # ------------------------------------------------------------------
    # Vérification d'agent
    # ------------------------------------------------------------------

    def _check_agent(self, agent: Optional[Any], name: str) -> None:
        """Lève RuntimeError si l'agent est None."""
        if agent is None:
            raise RuntimeError(f"❌ {name} non disponible.")
