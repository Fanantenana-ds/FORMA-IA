"""
=============================================================================
PACKAGE : app.orchestrator
=============================================================================
Module   : Orchestrateurs IA — FORMA-IA
Rôle     : Regroupe les orchestrateurs qui coordonnent les agents IA
           des différents modules (M1, M2, M5).

Orchestrateurs disponibles :
---------------------------
    - VeilleOrchestrator    → Module M1 (Veille marché)
    - TdrOrchestrator       → Module M2 (Termes de Référence)
    - FormationOrchestrator → Module M5 (Gestion des Formations)
                              ├── Agent 1 : FormGenerator       ✅
                              ├── Agent 2 : LevelAnalyzer       ✅
                              ├── Agent 3 : SatisfactionAnalyzer ✅
                              ├── Agent 4 : PresenceAnalyzer    ✅
                              ├── Agent 5 : AttestationGenerator ✅
                              ├── Agent 6 : ReportGenerator     ✅
                              └── Agent 7 : KnowledgeBase (V2)  ⏳

Pattern :
---------
    - 1 orchestrateur = 1 point d'entrée unique par module
    - Async/await partout
    - Logs détaillés (emojis + durée + compteurs)
    - Délègue la logique métier aux services
    - Singleton via get_<module>_orchestrator()

Auteur  : Équipe IA — ALTIORA Solutions
Version : 1.1.0
=============================================================================
"""

import logging

# =============================================================================
# LOGGER
# =============================================================================
logger = logging.getLogger(__name__)


# =============================================================================
# MÉTADONNÉES DU PACKAGE
# =============================================================================
__version__ = "1.1.0"
__author__ = "Équipe IA — ALTIORA Solutions"

__all__ = [
    "__version__",
    "__author__",
    "get_orchestrator_status",
]


# =============================================================================
# FONCTION UTILITAIRE — ÉTAT DU PACKAGE
# =============================================================================

def get_orchestrator_status() -> dict:
    """
    Retourne l'état d'implémentation des orchestrateurs.

    Utile pour :
        - Debug au démarrage de l'application
        - Endpoint de monitoring : GET /health/orchestrators
        - Logs de démarrage FastAPI

    Returns:
        dict: État de chaque orchestrateur (✅ disponible / ⏳ indisponible)
    """
    status = {
        "package": "app.orchestrator",
        "version": __version__,
        "orchestrators": {
            "VeilleOrchestrator":    VeilleOrchestrator is not None,
            "TdrOrchestrator":       TdrOrchestrator is not None,
            "FormationOrchestrator": FormationOrchestrator is not None,
        },
    }
    status["available_count"] = sum(1 for v in status["orchestrators"].values() if v)
    status["total"] = len(status["orchestrators"])
    return status


# =============================================================================
# IMPORT — VeilleOrchestrator (M1)
# =============================================================================
VeilleOrchestrator = None
try:
    from .veille_orchestrator import VeilleOrchestrator
    __all__.append("VeilleOrchestrator")
    logger.debug("✅ [orchestrator] VeilleOrchestrator importé (M1)")
except ImportError as e:
    logger.warning(f"⚠️  [orchestrator] VeilleOrchestrator indisponible : {e}")


# =============================================================================
# IMPORT — TdrOrchestrator (M2)
# =============================================================================
TdrOrchestrator = None
try:
    from .tdr_orchestrator import TdrOrchestrator
    __all__.append("TdrOrchestrator")
    logger.debug("✅ [orchestrator] TdrOrchestrator importé (M2)")
except ImportError as e:
    logger.warning(f"⚠️  [orchestrator] TdrOrchestrator indisponible : {e}")


# =============================================================================
# IMPORT — FormationOrchestrator (M5)
# =============================================================================
FormationOrchestrator = None
get_formation_orchestrator = None
try:
    from .formation_orchestrator import (
        FormationOrchestrator,
        get_formation_orchestrator,
    )
    __all__.append("FormationOrchestrator")
    __all__.append("get_formation_orchestrator")
    logger.debug("✅ [orchestrator] FormationOrchestrator importé (M5)")
except ImportError as e:
    logger.warning(f"⚠️  [orchestrator] FormationOrchestrator indisponible : {e}")


# =============================================================================
# LOG DE CHARGEMENT DU PACKAGE
# =============================================================================
_status = get_orchestrator_status()
_ready = [k for k, v in _status["orchestrators"].items() if v]
logger.info(
    f"📦 Package 'orchestrator' (v{__version__}) chargé — "
    f"{_status['available_count']}/{_status['total']} orchestrateurs "
    f"{'[' + ', '.join(_ready) + ']' if _ready else '[aucun]'}"
)