import logging

logger = logging.getLogger(__name__)


# =============================================================================
# MÉTADONNÉES
# =============================================================================
__version__ = "1.0.0"
__module_code__ = "M3"
__module_name__ = "Offres techniques et financières"
__author__ = "Équipe IA — ALTIORA Prest"


__all__ = [
    "__version__",
    "__module_code__",
    "__module_name__",
    "GrilleTarifaireService",
    "OffreTechniqueGeneratorService",
    "OffreFinanciereGeneratorService",
    "get_package_status",
]


# =============================================================================
# IMPORT — GrilleTarifaireService (Python pur)
# =============================================================================
GrilleTarifaireService = None
try:
    from .grille_tarifaire_service import GrilleTarifaireService
    __all__.append("GrilleTarifaireService")
    logger.debug("✅ [offres] GrilleTarifaireService importé")
except ImportError as e:
    logger.warning(f"⚠️  [offres] GrilleTarifaireService indisponible : {e}")


# =============================================================================
# IMPORT — OffreTechniqueGeneratorService (Agent M3-1)
# =============================================================================
OffreTechniqueGeneratorService = None
try:
    from .offre_technique_service import OffreTechniqueGeneratorService
    __all__.append("OffreTechniqueGeneratorService")
    logger.debug("✅ [offres] Agent M3-1 — OffreTechniqueGeneratorService importé")
except ImportError as e:
    logger.warning(f"⚠️  [offres] Agent M3-1 indisponible : {e}")


# =============================================================================
# IMPORT — OffreFinanciereGeneratorService (Agent M3-2)
# =============================================================================
OffreFinanciereGeneratorService = None
try:
    from .offre_financiere_service import OffreFinanciereGeneratorService
    __all__.append("OffreFinanciereGeneratorService")
    logger.debug("✅ [offres] Agent M3-2 — OffreFinanciereGeneratorService importé")
except ImportError as e:
    logger.warning(f"⚠️  [offres] Agent M3-2 indisponible : {e}")


# =============================================================================
# FONCTION UTILITAIRE — ÉTAT DU PACKAGE
# =============================================================================

def get_package_status() -> dict:
    """Retourne l'état d'implémentation du package M3."""
    status = {
        "module": __module_code__,
        "module_name": __module_name__,
        "version": __version__,
        "services": {
            "GrilleTarifaireService":              GrilleTarifaireService is not None,
            "Agent M3-1 — OffreTechnique":         OffreTechniqueGeneratorService is not None,
            "Agent M3-2 — OffreFinanciere":        OffreFinanciereGeneratorService is not None,
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