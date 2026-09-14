import logging

logger = logging.getLogger(__name__)


# =============================================================================
# MÉTADONNÉES
# =============================================================================
__version__ = "1.6.0"
__module_code__ = "M5"
__module_name__ = "Gestion des Formations"
__author__ = "Équipe IA — ALTIORA Solutions"

__all__ = [
    "__version__",
    "__module_code__",
    "__module_name__",
    "get_package_status",
]


# =============================================================================
# AGENT 1 — FormGeneratorService
# =============================================================================
FormGeneratorService = None
try:
    from .form_generator_service import FormGeneratorService
    __all__.append("FormGeneratorService")
    logger.debug("✅ [formations] Agent 1 — FormGeneratorService importé")
except ImportError as e:
    logger.warning(f"⚠️  [formations] Agent 1 indisponible : {e}")


# =============================================================================
# AGENT 2 — LevelAnalyzerService
# =============================================================================
LevelAnalyzerService = None
try:
    from .level_analyzer_service import LevelAnalyzerService
    __all__.append("LevelAnalyzerService")
    logger.debug("✅ [formations] Agent 2 — LevelAnalyzerService importé")
except ImportError as e:
    logger.warning(f"⚠️  [formations] Agent 2 indisponible : {e}")


# =============================================================================
# AGENT 3 — SatisfactionAnalyzerService
# =============================================================================
SatisfactionAnalyzerService = None
try:
    from .satisfaction_analyzer_service import SatisfactionAnalyzerService
    __all__.append("SatisfactionAnalyzerService")
    logger.debug("✅ [formations] Agent 3 — SatisfactionAnalyzerService importé")
except ImportError as e:
    logger.warning(f"⚠️  [formations] Agent 3 indisponible : {e}")


# =============================================================================
# AGENT 4 — PresenceAnalyzerService
# =============================================================================
PresenceAnalyzerService = None
try:
    from .presence_analyzer_service import PresenceAnalyzerService
    __all__.append("PresenceAnalyzerService")
    logger.debug("✅ [formations] Agent 4 — PresenceAnalyzerService importé")
except ImportError as e:
    logger.warning(f"⚠️  [formations] Agent 4 indisponible : {e}")


# =============================================================================
# AGENT 5 — AttestationGeneratorService
# =============================================================================
AttestationGeneratorService = None
try:
    from .attestation_generator_service import AttestationGeneratorService
    __all__.append("AttestationGeneratorService")
    logger.debug("✅ [formations] Agent 5 — AttestationGeneratorService importé")
except ImportError as e:
    logger.warning(f"⚠️  [formations] Agent 5 indisponible : {e}")


# =============================================================================
# AGENT 6 — ReportGeneratorService
# =============================================================================
ReportGeneratorService = None
try:
    from .report_generator_service import ReportGeneratorService
    __all__.append("ReportGeneratorService")
    logger.debug("✅ [formations] Agent 6 — ReportGeneratorService importé")
except ImportError as e:
    logger.warning(f"⚠️  [formations] Agent 6 indisponible : {e}")


# =============================================================================
# AGENT 7 — KnowledgeBaseService (V2)
# =============================================================================
KnowledgeBaseService = None
try:
    from .knowledge_base_service import KnowledgeBaseService  # type: ignore
    __all__.append("KnowledgeBaseService")
    logger.debug("✅ [formations] Agent 7 — KnowledgeBaseService importé")
except ImportError:
    logger.debug("⏳ [formations] Agent 7 non implémenté (V2)")


# =============================================================================
# FONCTION UTILITAIRE — ÉTAT DU PACKAGE
# =============================================================================

def get_package_status() -> dict:
    """
    Retourne l'état d'implémentation des agents du package M5.

    Utile pour :
        - Debug au démarrage de l'application
        - Endpoint de monitoring : GET /health/m5
        - Logs de démarrage FastAPI

    Returns:
        dict: État de chaque agent (✅ implémenté / ⏳ en attente)
    """
    status = {
        "module": __module_code__,
        "module_name": __module_name__,
        "version": __version__,
        "agents": {
            "Agent 1 — FormGenerator":          FormGeneratorService is not None,
            "Agent 2 — LevelAnalyzer":          LevelAnalyzerService is not None,
            "Agent 3 — SatisfactionAnalyzer":   SatisfactionAnalyzerService is not None,
            "Agent 4 — PresenceAnalyzer":       PresenceAnalyzerService is not None,
            "Agent 5 — AttestationGenerator":   AttestationGeneratorService is not None,
            "Agent 6 — ReportGenerator":        ReportGeneratorService is not None,
            "Agent 7 — KnowledgeBase (RAG V2)": KnowledgeBaseService is not None,
        },
    }
    status["implemented_count"] = sum(1 for v in status["agents"].values() if v)
    status["total_agents"] = len(status["agents"])
    return status


# =============================================================================
# LOG DE CHARGEMENT DU PACKAGE
# =============================================================================
_status = get_package_status()
_ready = [name.split(" — ")[0] for name, ok in _status["agents"].items() if ok]
logger.info(
    f"📦 Package '{__module_name__}' ({__module_code__} v{__version__}) chargé — "
    f"{_status['implemented_count']}/{_status['total_agents']} agents actifs "
    f"{'[' + ', '.join(_ready) + ']' if _ready else '[aucun agent]'}"
)