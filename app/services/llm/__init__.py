"""
=============================================================================
PACKAGE : app.services.llm
=============================================================================
Rôle     : Fournisseur LLM avec Provider Abstraction.
=============================================================================
"""

import logging

logger = logging.getLogger(__name__)


# =============================================================================
# MÉTADONNÉES
# =============================================================================
__version__ = "1.0.0"
__author__ = "Équipe IA — ALTIORA Prest"


# =============================================================================
# IMPORTS
# =============================================================================
from .llm_provider import LLMProvider
from .groq_provider import GroqProvider
from .claude_provider import ClaudeProvider
from .llm_factory import get_llm_provider, get_provider_info


# =============================================================================
# EXPORTS
# =============================================================================
__all__ = [
    "__version__",
    "LLMProvider",
    "GroqProvider",
    "ClaudeProvider",
    "get_llm_provider",
    "get_provider_info",
]


# =============================================================================
# LOG DE CHARGEMENT
# =============================================================================
logger.info(
    f"📦 Package 'llm' (Provider Abstraction v{__version__}) chargé — "
    f"Providers : GroqProvider, ClaudeProvider"
)