"""
=============================================================================
IMPLÉMENTATION : ClaudeProvider (V3 — Placeholder)
=============================================================================
Rôle     : Fournisseur LLM basé sur l'API Anthropic Claude.

⚠️ STATUT : Placeholder prêt pour V3.
    - La structure est complète
    - L'appel réel sera activé quand la clé API payante sera disponible
    - Le code métier (agents 1-6) NE CHANGE PAS — seule la config .env change

Modèle   : claude-3-5-sonnet-20241022 (configurable via .env)
API      : https://api.anthropic.com/v1/messages

Auteur  : Équipe IA — ALTIORA Prest
Version : 1.0.0 (placeholder)
=============================================================================
"""

import os
import logging
from typing import Dict, Any, Optional

from .llm_provider import (
    LLMProvider,
    LLMError,
    LLMTimeoutError,
    LLMRateLimitError,
    LLMInvalidResponseError,
    LLMNotAvailableError,
)

logger = logging.getLogger(__name__)

VERBOSE = os.getenv("VERBOSE_LOGS", "true").lower() == "true"


def vlog(msg: str, level: str = "info") -> None:
    if VERBOSE:
        getattr(logger, level)(msg)


# =============================================================================
# PROVIDER CLAUDE
# =============================================================================

class ClaudeProvider(LLMProvider):
    """
    Fournisseur LLM basé sur Anthropic Claude API.

    ⚠️ PLACEHOLDER — À ACTIVER EN V3 quand la clé API sera disponible.

    Configuration via variables d'environnement :
        - ANTHROPIC_API_KEY   (obligatoire pour V3)
        - ANTHROPIC_MODEL     (défaut: claude-3-5-sonnet-20241022)
    """

    def __init__(self):
        self.api_key = os.getenv("ANTHROPIC_API_KEY", "").strip()
        self.model = os.getenv(
            "ANTHROPIC_MODEL", "claude-3-5-sonnet-20241022"
        ).strip()

        # ⚠️ Le client Anthropic sera initialisé quand la clé sera disponible.
        self.client = None

        if not self.api_key:
            logger.info(
                "ℹ️  ClaudeProvider : ANTHROPIC_API_KEY non configurée. "
                "Provider en attente (V3)."
            )
        else:
            # TODO V3 : initialiser le client Anthropic ici
            # from anthropic import AsyncAnthropic
            # self.client = AsyncAnthropic(api_key=self.api_key)
            vlog(
                f"✅ ClaudeProvider initialisé "
                f"(model={self.model}, mode=V3)"
            )

    # =========================================================================
    # MÉTHODES ABSTRAITES
    # =========================================================================

    async def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.4,
        max_tokens: int = 4000,
        json_mode: bool = True,
        reasoning_effort: Optional[str] = None,
        timeout: Optional[float] = None,
    ) -> Dict[str, Any]:
        """
        Génère une réponse via Claude API.

        ⚠️ PLACEHOLDER — L'implémentation réelle sera ajoutée en V3.
        reasoning_effort est propre aux modèles Groq : Claude n'a pas
        d'équivalent, le paramètre est accepté (conformité d'interface)
        mais ignoré.
        """
        if not self.is_available():
            raise LLMNotAvailableError(
                "❌ ClaudeProvider non disponible. "
                "ANTHROPIC_API_KEY manquante ou client non initialisé. "
                "Ce provider sera activé en V3."
            )

        # ─────────────────────────────────────────────────────────────
        # TODO V3 : Implémentation réelle de l'appel Claude
        # ─────────────────────────────────────────────────────────────
        #
        # Exemple de code pour V3 :
        #
        # response = await self.client.messages.create(
        #     model=self.model,
        #     max_tokens=max_tokens,
        #     temperature=temperature,
        #     system=system_prompt,
        #     messages=[
        #         {"role": "user", "content": user_prompt}
        #     ],
        # )
        #
        # content = response.content[0].text
        # finish_reason = response.stop_reason or "stop"
        # usage = {
        #     "prompt_tokens": response.usage.input_tokens,
        #     "completion_tokens": response.usage.output_tokens,
        #     "total_tokens": response.usage.input_tokens + response.usage.output_tokens,
        # }
        #
        # return {
        #     "content": content,
        #     "finish_reason": finish_reason,
        #     "usage": usage,
        #     "model": self.model,
        #     "provider": "claude",
        # }
        #
        # ─────────────────────────────────────────────────────────────

        raise LLMNotAvailableError(
            "⚠️  ClaudeProvider : implémentation V3 non encore active. "
            "Utilisez LLM_PROVIDER=groq dans .env."
        )

    def get_model_name(self) -> str:
        return self.model

    def get_provider_name(self) -> str:
        return "claude"

    def is_available(self) -> bool:
        """
        Vérifie si le provider est prêt.

        ⚠️ Retourne False tant que l'implémentation V3 n'est pas faite.
        """
        # TODO V3 : activer quand le client sera initialisé
        # return self.client is not None and bool(self.api_key)
        return False