import os
import json
import logging
from typing import Dict, Any

from openai import AsyncOpenAI
from openai import (
    APITimeoutError,
    RateLimitError,
    APIError,
    APIConnectionError,
)

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
# PROVIDER GROQ
# =============================================================================

class GroqProvider(LLMProvider):
    """
    Fournisseur LLM basé sur Groq API.

    Configuration via variables d'environnement :
        - GROQ_API_KEY   (obligatoire)
        - GROQ_MODEL     (défaut: openai/gpt-oss-20b)
        - GROQ_BASE_URL  (défaut: https://api.groq.com/openai/v1)
    """

    def __init__(self):
        self.api_key = os.getenv("GROQ_API_KEY", "").strip()
        self.model = os.getenv("GROQ_MODEL", "openai/gpt-oss-20b").strip()
        self.base_url = os.getenv(
            "GROQ_BASE_URL", "https://api.groq.com/openai/v1"
        ).strip()

        if not self.api_key:
            logger.warning(
                "⚠️  GroqProvider : GROQ_API_KEY manquante. "
                "Le provider ne sera pas disponible."
            )
            self.client = None
        else:
            self.client = AsyncOpenAI(
                api_key=self.api_key,
                base_url=self.base_url,
            )
            vlog(
                f"✅ GroqProvider initialisé "
                f"(model={self.model}, base_url={self.base_url})"
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
    ) -> Dict[str, Any]:
        """Génère une réponse via Groq API."""
        if not self.is_available():
            raise LLMNotAvailableError(
                "❌ GroqProvider non disponible (clé API manquante)."
            )

        vlog(
            f"🚀 [GroqProvider] generate() — "
            f"model={self.model}, json_mode={json_mode}, "
            f"max_tokens={max_tokens}"
        )

        # Construire les kwargs de base
        kwargs: Dict[str, Any] = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        # ⚠️ IMPORTANT : PAS de response_format="json_object"
        # (casse la validation stricte Groq sur certains prompts — cf. bug \')
        # On extrait le JSON manuellement dans les services si nécessaire.

        try:
            response = await self.client.chat.completions.create(**kwargs)

            content = response.choices[0].message.content or ""
            finish_reason = response.choices[0].finish_reason or "stop"

            usage = {
                "prompt_tokens": getattr(response.usage, "prompt_tokens", 0),
                "completion_tokens": getattr(response.usage, "completion_tokens", 0),
                "total_tokens": getattr(response.usage, "total_tokens", 0),
            }

            vlog(
                f"✅ [GroqProvider] Réponse reçue — "
                f"{len(content)} chars, finish={finish_reason}, "
                f"tokens={usage['total_tokens']}"
            )

            return {
                "content": content,
                "finish_reason": finish_reason,
                "usage": usage,
                "model": self.model,
                "provider": "groq",
            }

        except APITimeoutError as e:
            logger.error(f"❌ [GroqProvider] Timeout : {e}")
            raise LLMTimeoutError(f"Timeout Groq : {e}") from e

        except RateLimitError as e:
            logger.error(f"❌ [GroqProvider] Rate limit : {e}")
            raise LLMRateLimitError(f"Rate limit Groq : {e}") from e

        except APIConnectionError as e:
            logger.error(f"❌ [GroqProvider] Erreur connexion : {e}")
            raise LLMError(f"Erreur connexion Groq : {e}") from e

        except APIError as e:
            logger.error(f"❌ [GroqProvider] Erreur API : {e}")
            raise LLMError(f"Erreur API Groq : {e}") from e

        except json.JSONDecodeError as e:
            logger.error(f"❌ [GroqProvider] JSON invalide : {e}")
            raise LLMInvalidResponseError(f"JSON invalide : {e}") from e

        except Exception as e:
            logger.exception(f"❌ [GroqProvider] Erreur inattendue : {e}")
            raise LLMError(f"Erreur Groq inattendue : {e}") from e

    def get_model_name(self) -> str:
        return self.model

    def get_provider_name(self) -> str:
        return "groq"

    def is_available(self) -> bool:
        return self.client is not None and bool(self.api_key)