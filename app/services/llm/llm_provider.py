from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List


# =============================================================================
# EXCEPTIONS PERSONNALISÉES
# =============================================================================

class LLMError(Exception):
    """Exception de base pour toutes les erreurs LLM."""
    pass


class LLMTimeoutError(LLMError):
    """Timeout dépassé lors de l'appel au LLM."""
    pass


class LLMRateLimitError(LLMError):
    """Quota API dépassé (rate limit)."""
    pass


class LLMInvalidResponseError(LLMError):
    """Réponse invalide du LLM (JSON malformé, etc.)."""
    pass


class LLMNotAvailableError(LLMError):
    """Fournisseur LLM non disponible (clé API manquante, etc.)."""
    pass


# =============================================================================
# INTERFACE ABSTRAITE
# =============================================================================

class LLMProvider(ABC):
    """
    Interface abstraite pour tous les fournisseurs LLM.

    ⚠️ Toute implémentation DOIT hériter de cette classe et
       implémenter les méthodes abstraites ci-dessous.
    """

    # =========================================================================
    # MÉTHODES ABSTRAITES (à implémenter)
    # =========================================================================

    @abstractmethod
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
        Génère une réponse à partir d'un prompt système et utilisateur.

        Args:
            system_prompt: Prompt système (rôle, règles, contexte).
            user_prompt: Prompt utilisateur (tâche, données).
            temperature: Créativité (0.0 = déterministe, 1.0 = créatif).
            max_tokens: Nombre maximum de tokens en sortie.
            json_mode: Si True, force la réponse au format JSON.
            reasoning_effort: Paramètre spécifique aux modèles de raisonnement
                Groq ("low"/"medium"/"high"). None = comportement par défaut
                du provider. Un provider qui ne le supporte pas (Claude)
                l'ignore silencieusement.
            timeout: Délai maximum en secondes pour CET appel (None =
                délai par défaut du client). Le provider est un singleton
                partagé entre appelants aux besoins différents (M1 veut un
                délai court, M2 un délai long) : ce paramètre s'applique
                par appel, pas à la construction du client.

        Returns:
            {
                "content": str,          # Contenu de la réponse
                "finish_reason": str,    # "stop" ou "length"
                "usage": {               # Statistiques tokens
                    "prompt_tokens": int,
                    "completion_tokens": int,
                    "total_tokens": int,
                },
                "model": str,            # Nom du modèle utilisé
                "provider": str,         # "groq" ou "claude"
            }

        Raises:
            LLMError: En cas d'erreur générale.
            LLMTimeoutError: En cas de timeout.
            LLMRateLimitError: En cas de quota dépassé.
            LLMInvalidResponseError: En cas de réponse invalide.
        """
        pass

    @abstractmethod
    def get_model_name(self) -> str:
        """Retourne le nom du modèle utilisé (ex: 'openai/gpt-oss-20b')."""
        pass

    @abstractmethod
    def get_provider_name(self) -> str:
        """Retourne le nom du fournisseur (ex: 'groq' ou 'claude')."""
        pass

    @abstractmethod
    def is_available(self) -> bool:
        """Vérifie si le provider est correctement configuré (clé API, etc.)."""
        pass

    # =========================================================================
    # MÉTHODES CONCRÈTES (implémentées ici pour tous les providers)
    # =========================================================================

    async def generate_with_retry(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.4,
        max_tokens: int = 4000,
        json_mode: bool = True,
        reasoning_effort: Optional[str] = None,
        timeout: Optional[float] = None,
        max_retries: int = 3,
        backoff_factor: float = 2.0,
    ) -> Dict[str, Any]:
        """
        Génère une réponse avec retry automatique (backoff exponentiel).

        Args:
            Idem `generate()` + :
            max_retries: Nombre maximum de tentatives (défaut: 3).
            backoff_factor: Multiplicateur du délai entre tentatives.

        Returns:
            Idem `generate()`.

        Raises:
            LLMError: Si toutes les tentatives échouent.
        """
        import asyncio

        last_error: Optional[Exception] = None
        delay = 1.0

        for attempt in range(1, max_retries + 1):
            try:
                return await self.generate(
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    json_mode=json_mode,
                    reasoning_effort=reasoning_effort,
                    timeout=timeout,
                )
            except LLMRateLimitError as e:
                # Rate limit → backoff obligatoire
                last_error = e
                if attempt < max_retries:
                    await asyncio.sleep(delay)
                    delay *= backoff_factor
            except LLMTimeoutError as e:
                # Timeout → retry avec backoff
                last_error = e
                if attempt < max_retries:
                    await asyncio.sleep(delay)
                    delay *= backoff_factor
            except LLMError as e:
                # Autres erreurs → pas de retry (échec immédiat)
                raise e

        # Toutes les tentatives ont échoué
        raise LLMError(
            f"❌ Échec après {max_retries} tentatives. "
            f"Dernière erreur : {last_error}"
        )

    async def generate_multi_messages(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.4,
        max_tokens: int = 4000,
        json_mode: bool = True,
    ) -> Dict[str, Any]:
        """
        Génère une réponse à partir d'une liste de messages
        (format conversationnel).

        Args:
            messages: Liste de dicts : [{"role": "system"|"user"|"assistant",
                                          "content": "..."}]
            Autres : idem `generate()`.

        Returns:
            Idem `generate()`.
        """
        # Extraire system + user depuis la liste
        system_prompt = ""
        user_parts = []

        for msg in messages:
            role = msg.get("role", "")
            content = msg.get("content", "")

            if role == "system":
                system_prompt += content + "\n"
            elif role == "user":
                user_parts.append(content)
            elif role == "assistant":
                user_parts.append(f"[Précédent] {content}")

        user_prompt = "\n\n".join(user_parts)

        return await self.generate(
            system_prompt=system_prompt.strip(),
            user_prompt=user_prompt.strip(),
            temperature=temperature,
            max_tokens=max_tokens,
            json_mode=json_mode,
        )