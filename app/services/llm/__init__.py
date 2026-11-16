import logging

logger = logging.getLogger(__name__)


# =============================================================================
# MÉTADONNÉES
# =============================================================================
__version__ = "1.0.0"
__author__ = "Équipe IA — ALTIORA Prest"


# =============================================================================
# IMPORTS — INTERFACE + EXCEPTIONS
# =============================================================================
from .claude_provider import ClaudeProvider

# =============================================================================
# IMPORTS — IMPLÉMENTATIONS
# =============================================================================
from .groq_provider import GroqProvider

# =============================================================================
# IMPORTS — FACTORY
# =============================================================================
from .llm_factory import get_llm_provider, get_provider_info, reset_providers_cache
from .llm_provider import (
    LLMError,
    LLMInvalidResponseError,
    LLMNotAvailableError,
    LLMProvider,
    LLMRateLimitError,
    LLMTimeoutError,
)

# =============================================================================
# EXPORTS
# =============================================================================
__all__ = [
    "__version__",
    # Interface
    "LLMProvider",
    # Exceptions
    "LLMError",
    "LLMTimeoutError",
    "LLMRateLimitError",
    "LLMInvalidResponseError",
    "LLMNotAvailableError",
    # Implémentations
    "GroqProvider",
    "ClaudeProvider",
    # Factory
    "get_llm_provider",
    "get_provider_info",
    "reset_providers_cache",
]


# =============================================================================
# LOG DE CHARGEMENT
# =============================================================================
logger.info(
    f"📦 Package 'llm' (Provider Abstraction v{__version__}) chargé — "
    f"Providers : GroqProvider, ClaudeProvider"
)