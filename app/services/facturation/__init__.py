import logging

logger = logging.getLogger(__name__)


# =============================================================================
# MÉTADONNÉES
# =============================================================================
__version__ = "1.0.0"
__module_code__ = "M7"
__module_name__ = "Facturation et relances"
__author__ = "Équipe IA — ALTIORA Prest"

__all__ = [
    "__version__",
    "__module_code__",
    "__module_name__",
    "RelanceGeneratorService",
    "get_package_status",
]


# =============================================================================
# IMPORT — RelanceGeneratorService (Agent M7)
# =============================================================================
RelanceGeneratorService = None
try:
    from .relance_generator_service import RelanceGeneratorService
    __all__.append("RelanceGeneratorService")
    logger.debug("✅ [facturation] Agent M7 — RelanceGeneratorService importé")
except ImportError as e:
    logger.warning(f"⚠️  [facturation] Agent M7 indisponible : {e}")


# =============================================================================
# FONCTION UTILITAIRE — ÉTAT DU PACKAGE
# =============================================================================

def get_package_status() -> dict:
    """Retourne l'état d'implémentation du package M7."""
    status = {
        "module": __module_code__,
        "module_name": __module_name__,
        "version": __version__,
        "services": {
            "Agent M7 — RelanceGenerator": RelanceGeneratorService is not None,
        },
    }
    status["implemented_count"] = sum(1 for v in status["services"].values() if v)
    status["total_services"] = len(status["services"])
    return status


# =============================================================================
# LOG DE CHARGEMENT
# =============================================================================
_status = get_package_status()
logger.info(
    f"📦 Package '{__module_name__}' ({__module_code__} v{__version__}) chargé — "
    f"{_status['implemented_count']}/{_status['total_services']} services actifs"
)
