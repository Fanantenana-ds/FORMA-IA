# app/utils/retry.py
# ============================================================
# RETRY AVEC BACKOFF EXPONENTIEL (CDC §6.2)
# ============================================================
# Utilitaire générique, partagé par tous les services qui font
# des appels réseau (Tavily, Groq, sync backend...).
# ============================================================

import asyncio
import logging
import random
from typing import Optional

logger = logging.getLogger(__name__)


async def retry_with_backoff(
    coro_func,
    *args,
    max_retries: int = 3,
    base_delay: float = 1.0,
    retryable_exceptions=(Exception,),
    label: str = "appel réseau",
    **kwargs,
):
    """
    Exécute coro_func(*args, **kwargs) avec retry + backoff
    exponentiel + jitter.

    Ne retry QUE sur les exceptions listées dans
    retryable_exceptions (par défaut : tout, à restreindre par
    l'appelant aux erreurs transitoires — jamais une erreur de
    parsing/logique métier).
    """
    last_exc: Optional[Exception] = None

    for attempt in range(max_retries):
        try:
            return await coro_func(*args, **kwargs)

        except retryable_exceptions as exc:
            last_exc = exc

            if attempt == max_retries - 1:
                break

            delay = base_delay * (2 ** attempt) + random.uniform(0, 0.5)

            logger.warning(
                "⚠️ %s — tentative %d/%d échouée (%s), retry dans %.1fs",
                label,
                attempt + 1,
                max_retries,
                exc,
                delay,
            )

            await asyncio.sleep(delay)

    logger.error(
        "❌ %s — échec définitif après %d tentatives : %s",
        label,
        max_retries,
        last_exc,
    )

    raise last_exc