import os
import logging
from typing import Optional, Dict, Any

from .llm_provider import LLMProvider, LLMNotAvailableError
from .groq_provider import GroqProvider
from .claude_provider import ClaudeProvider

logger = logging.getLogger(__name__)

VERBOSE = os.getenv("VERBOSE_LOGS", "true").lower() == "true"


def vlog(msg: str, level: str = "info") -> None:
    if VERBOSE:
        getattr(logger, level)(msg)


# =============================================================================
# CACHE DES INSTANCES (Singleton par provider)
# =============================================================================

_providers_cache: Dict[str, LLMProvider] = {}


# =============================================================================
# FONCTION PRINCIPALE
# =============================================================================

def get_llm_provider(force_provider: Optional[str] = None) -> LLMProvider:
    """
    Retourne l'instance du provider LLM configuré.

    Args:
        force_provider: Optionnel. Force un provider spécifique
            ("groq" ou "claude"). Utile pour les tests.

    Returns:
        Instance de LLMProvider (GroqProvider ou ClaudeProvider).

    Raises:
        LLMNotAvailableError: Si aucun provider n'est disponible.
    """
    # Déterminer quel provider utiliser
    provider_name = (
        force_provider or os.getenv("LLM_PROVIDER", "groq")
    ).lower().strip()

    vlog(f"🔧 [LLM Factory] Provider demandé : '{provider_name}'")

    # ─────────────────────────────────────────────────────────────
    # CAS 1 : Provider déjà en cache → retour immédiat
    # ─────────────────────────────────────────────────────────────
    if provider_name in _providers_cache:
        vlog(f"   ✅ Provider '{provider_name}' récupéré du cache")
        return _providers_cache[provider_name]

    # ─────────────────────────────────────────────────────────────
    # CAS 2 : Provider à instancier
    # ─────────────────────────────────────────────────────────────
    provider: Optional[LLMProvider] = None

    if provider_name == "groq":
        provider = GroqProvider()

    elif provider_name == "claude":
        provider = ClaudeProvider()
        # ⚠️ Si Claude n'est pas disponible → fallback Groq
        if not provider.is_available():
            logger.warning(
                "⚠️  ClaudeProvider non disponible → fallback GroqProvider"
            )
            provider = GroqProvider()
            provider_name = "groq"

    else:
        logger.error(
            f"❌ Provider inconnu : '{provider_name}'. "
            f"Valeurs acceptées : 'groq', 'claude'."
        )
        raise LLMNotAvailableError(
            f"Provider LLM inconnu : '{provider_name}'. "
            f"Vérifiez LLM_PROVIDER dans .env."
        )

    # ─────────────────────────────────────────────────────────────
    # Vérifier la disponibilité
    # ─────────────────────────────────────────────────────────────
    if provider is None or not provider.is_available():
        logger.error(
            f"❌ Provider '{provider_name}' non disponible "
            f"(clé API manquante ?)"
        )
        raise LLMNotAvailableError(
            f"Provider LLM '{provider_name}' non disponible. "
            f"Vérifiez la configuration dans .env."
        )

    # ─────────────────────────────────────────────────────────────
    # Mettre en cache
    # ─────────────────────────────────────────────────────────────
    _providers_cache[provider_name] = provider
    vlog(
        f"✅ [LLM Factory] Provider '{provider_name}' instancié et mis en cache "
        f"(model={provider.get_model_name()})"
    )

    return provider


# =============================================================================
# FONCTION UTILITAIRE — INFO PROVIDER
# =============================================================================

def get_provider_info() -> Dict[str, Any]:
    """
    Retourne les informations sur le provider actif.

    Utile pour :
        - Endpoint de monitoring : GET /health/llm
        - Logs de démarrage FastAPI
        - Debug

    Returns:
        {
            "provider": str,           # "groq" ou "claude"
            "model": str,              # Nom du modèle
            "available": bool,         # Disponible ou non
            "fallback_active": bool,   # True si fallback Groq activé
            "config": {                # Config brute (sans secrets)
                "llm_provider_env": str,
                "groq_key_set": bool,
                "anthropic_key_set": bool,
            }
        }
    """
    try:
        provider = get_llm_provider()
        provider_name = provider.get_provider_name()
        model = provider.get_model_name()
        available = provider.is_available()
    except LLMNotAvailableError:
        provider_name = "none"
        model = "none"
        available = False

    return {
        "provider": provider_name,
        "model": model,
        "available": available,
        "fallback_active": provider_name == "groq"
            and os.getenv("LLM_PROVIDER", "groq").lower() == "claude",
        "config": {
            "llm_provider_env": os.getenv("LLM_PROVIDER", "groq"),
            "groq_key_set": bool(os.getenv("GROQ_API_KEY", "").strip()),
            "anthropic_key_set": bool(os.getenv("ANTHROPIC_API_KEY", "").strip()),
        },
    }


# =============================================================================
# FONCTION UTILITAIRE — RESET (tests)
# =============================================================================

def reset_providers_cache() -> None:
    """Vide le cache des providers (utile pour les tests)."""
    global _providers_cache
    _providers_cache.clear()
    vlog("🔄 [LLM Factory] Cache des providers réinitialisé")