"""
=============================================================================
PACKAGE : app.services.preparation
=============================================================================
Module   : Préparation de la Formation (Étape 3 — Pipeline)
Rôle     : Services IA pour la préparation d'une formation.

Services :
    - BudgetCalculatorService  — Python pur (calculs déterministes)
    - EDTGeneratorService      — LLM (Groq/Claude) + fallback

Auteur  : Équipe IA — ALTIORA Prest
Version : 1.0.0
=============================================================================
"""

import logging

logger = logging.getLogger(__name__)


# =============================================================================
# MÉTADONNÉES
# =============================================================================
__version__ = "1.0.0"
__module_code__ = "PREP"
__module_name__ = "Préparation de la Formation"
__author__ = "Équipe IA — ALTIORA Prest"


__all__ = [
    "__version__",
    "__module_code__",
    "__module_name__",
    "BudgetCalculatorService",
    "EDTGeneratorService",
    "get_package_status",
]


# =============================================================================
# IMPORT — BudgetCalculatorService (Python pur)
# =============================================================================
BudgetCalculatorService = None
try:
    from .budget_calculator_service import BudgetCalculatorService
    __all__.append("BudgetCalculatorService")
    logger.debug("✅ [preparation] BudgetCalculatorService importé")
except ImportError as e:
    logger.warning(f"⚠️  [preparation] BudgetCalculatorService indisponible : {e}")


# =============================================================================
# IMPORT — EDTGeneratorService (LLM)
# =============================================================================
EDTGeneratorService = None
try:
    from .edt_generator_service import EDTGeneratorService
    __all__.append("EDTGeneratorService")
    logger.debug("✅ [preparation] EDTGeneratorService importé")
except ImportError as e:
    logger.warning(f"⚠️  [preparation] EDTGeneratorService indisponible : {e}")


# =============================================================================
# FONCTION UTILITAIRE — ÉTAT DU PACKAGE
# =============================================================================

def get_package_status() -> dict:
    """Retourne l'état d'implémentation du package Préparation."""
    status = {
        "module": __module_code__,
        "module_name": __module_name__,
        "version": __version__,
        "services": {
            "BudgetCalculatorService":  BudgetCalculatorService is not None,
            "EDTGeneratorService":      EDTGeneratorService is not None,
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