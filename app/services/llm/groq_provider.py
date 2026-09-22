import os
import json
import logging
from typing import Dict, Any, Optional

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

# L'API Groq exige que le mot "json" apparaisse littéralement dans les
# messages envoyés quand response_format={"type": "json_object"} est utilisé
# (sinon erreur 400 : "'messages' must contain the word 'json'..."). Les
# prompts RTFCE du projet le mentionnent déjà (section FORMAT), mais ce
# filet de sécurité protège tout appelant, présent ou futur, qui l'oublierait.
_JSON_SAFETY_SUFFIX = (
    "\n\n===== FORMAT DE SORTIE =====\n"
    "Réponds UNIQUEMENT avec un objet JSON valide, sans texte avant ni "
    "après, sans bloc markdown."
)


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
        reasoning_effort: Optional[str] = None,
        timeout: Optional[float] = None,
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

        # json_mode=True : demande le mode JSON strict de Groq. Chaque
        # service appelant reste responsable d'extraire/réparer le JSON
        # lui-même (ce mode réduit le risque de texte parasite, il ne
        # garantit pas un JSON syntaxiquement valide à 100%).
        if json_mode and "json" not in (system_prompt + user_prompt).lower():
            user_prompt = user_prompt + _JSON_SAFETY_SUFFIX

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

        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}

        # Paramètre spécifique aux modèles de raisonnement Groq (ex:
        # openai/gpt-oss-20b/120b) : "medium" (défaut Groq) peut épuiser
        # tout le budget max_tokens en raisonnement interne avant de
        # produire le JSON final. "low" laisse plus de marge à la réponse.
        if reasoning_effort:
            kwargs["reasoning_effort"] = reasoning_effort

        # Délai par appel : le provider est un singleton partagé, les
        # appelants ont des besoins différents (M1 veut échouer vite, M2
        # tolère un délai plus long pour un document complet).
        if timeout is not None:
            kwargs["timeout"] = timeout

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