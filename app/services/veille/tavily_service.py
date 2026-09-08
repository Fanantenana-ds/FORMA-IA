# # app/services/veille/tavily_service.py
# # ============================================================
# # SERVICE TAVILY — recherche web uniquement
# # ============================================================
# # Responsabilité unique : interroger Tavily et retourner des
# # résultats bruts normalisés. Ne fait NI filtrage, NI scoring,
# # NI appel LLM.
# # ============================================================

# import logging
# import os
# import time
# from typing import Any, Dict, List

# import httpx

# from app.utils.retry import retry_with_backoff
# from app.utils.url_utils import normalize_url

# logger = logging.getLogger(__name__)

# TAVILY_API_KEY = os.getenv("TAVILY_API_KEY")
# MAX_RESULTS_TAVILY = int(os.getenv("MAX_RESULTS_TAVILY", "10"))
# TAVILY_TIMEOUT = float(os.getenv("TAVILY_TIMEOUT", "20"))
# RETRY_MAX_ATTEMPTS = int(os.getenv("RETRY_MAX_ATTEMPTS", "3"))
# RETRY_BASE_DELAY = float(os.getenv("RETRY_BASE_DELAY", "1.0"))


# class TavilyService:
#     """Recherche web via Tavily, avec retry/backoff (CDC §6.2)."""

#     def __init__(self):
#         if TAVILY_API_KEY:
#             logger.info("🔎 TAVILY configuré")
#         else:
#             logger.warning("⚠️ TAVILY_API_KEY absente")

#     async def _do_request(self, payload: Dict[str, Any]) -> httpx.Response:
#         """Un seul essai HTTP — rejouable par retry_with_backoff."""
#         async with httpx.AsyncClient(timeout=TAVILY_TIMEOUT) as client:
#             response = await client.post(
#                 "https://api.tavily.com/search",
#                 json=payload,
#             )
#             if response.status_code >= 500:
#                 response.raise_for_status()
#             return response

#     async def search(self, query: str) -> List[Dict[str, Any]]:
#         """Recherche Tavily et retourne des résultats normalisés."""

#         if not TAVILY_API_KEY:
#             logger.error("❌ TAVILY_API_KEY absente")
#             return []

#         payload = {
#             "api_key": TAVILY_API_KEY,
#             "query": f"{query} (Madagascar OR Antananarivo)",
#             "search_depth": "basic",
#             "max_results": MAX_RESULTS_TAVILY,
#             "include_raw_content": False,
#             "include_images": False,
#         }

#         start = time.perf_counter()

#         try:
#             response = await retry_with_backoff(
#                 self._do_request,
#                 payload,
#                 max_retries=RETRY_MAX_ATTEMPTS,
#                 base_delay=RETRY_BASE_DELAY,
#                 retryable_exceptions=(httpx.TimeoutException, httpx.HTTPError),
#                 label="Tavily",
#             )

#             elapsed = time.perf_counter() - start
#             logger.info("⏱️ Tavily : %.3fs", elapsed)

#             if response.status_code != 200:
#                 logger.error(
#                     "❌ Tavily HTTP %s : %s",
#                     response.status_code,
#                     response.text[:500],
#                 )
#                 return []

#             data = response.json()
#             raw_results = data.get("results", [])

#             if not isinstance(raw_results, list):
#                 return []

#             results = []
#             for result in raw_results:
#                 if not isinstance(result, dict):
#                     continue

#                 results.append({
#                     **result,
#                     "title": str(result.get("title", "")).strip(),
#                     "url": normalize_url(result.get("url", "")),
#                     "content": str(
#                         result.get("content", "") or result.get("snippet", "")
#                     ).strip(),
#                 })

#             logger.info("📊 Tavily : %d résultats", len(results))
#             return results

#         except (httpx.TimeoutException, httpx.HTTPError) as exc:
#             logger.error("❌ Tavily indisponible après retries : %s", exc)
#             return []

#         except Exception as exc:
#             logger.exception("❌ Tavily : %s", exc)
#             return []





# app/services/veille/tavily_service.py
# ============================================================
# SERVICE TAVILY — recherche web uniquement
# ============================================================
# Responsabilité unique : interroger Tavily et retourner des
# résultats bruts normalisés. Ne fait NI filtrage, NI scoring,
# NI appel LLM.
# ============================================================

import logging
import os
import re
import time
from typing import Any, Dict, List

import httpx

from app.utils.retry import retry_with_backoff
from app.utils.url_utils import normalize_url

logger = logging.getLogger(__name__)

TAVILY_API_KEY = os.getenv("TAVILY_API_KEY")
# 8 = exactement 2 lots complets de MAX_RESULTS_AI (4). Demander
# plus (ex: 10) n'apporte rien puisque le fallback par lots ne va
# jamais au-delà de 2 lots, et ralentit Tavily sans bénéfice.
MAX_RESULTS_TAVILY = int(os.getenv("MAX_RESULTS_TAVILY", "8"))
TAVILY_TIMEOUT = float(os.getenv("TAVILY_TIMEOUT", "20"))
RETRY_MAX_ATTEMPTS = int(os.getenv("RETRY_MAX_ATTEMPTS", "3"))
RETRY_BASE_DELAY = float(os.getenv("RETRY_BASE_DELAY", "1.0"))

# Motifs de bruit fréquents dans le contenu scrapé (murs de connexion
# réseaux sociaux, artefacts d'images, agrégateurs) — observés
# concrètement dans les logs de production (Facebook "Log In",
# "Forgot Account?", placeholders "Image N:").
NOISE_PATTERNS = [
    r"Log In\s*",
    r"Forgot Account\?\s*",
    r"Image \d+:\s*",
    r"Se connecter\s*",
    r"Mot de passe oubli[ée]\s*",
    r"S'inscrire\s*",
]


def clean_scraped_content(text: str) -> str:
    """
    Retire le bruit connu du contenu scrapé par Tavily avant qu'il
    ne soit envoyé au LLM. Réduit le budget de prompt gaspillé et
    le risque de confusion du modèle sur du texte non pertinent.
    """
    if not text:
        return text

    cleaned = text
    for pattern in NOISE_PATTERNS:
        cleaned = re.sub(pattern, "", cleaned, flags=re.IGNORECASE)

    # Compacte les sauts de ligne et espaces multiples résiduels.
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    cleaned = re.sub(r"[ \t]{2,}", " ", cleaned)

    return cleaned.strip()


class TavilyService:
    """Recherche web via Tavily, avec retry/backoff (CDC §6.2)."""

    def __init__(self):
        if TAVILY_API_KEY:
            logger.info("🔎 TAVILY configuré")
        else:
            logger.warning("⚠️ TAVILY_API_KEY absente")

    async def _do_request(self, payload: Dict[str, Any]) -> httpx.Response:
        """Un seul essai HTTP — rejouable par retry_with_backoff."""
        async with httpx.AsyncClient(timeout=TAVILY_TIMEOUT) as client:
            response = await client.post(
                "https://api.tavily.com/search",
                json=payload,
            )
            if response.status_code >= 500:
                response.raise_for_status()
            return response

    async def search(self, query: str) -> List[Dict[str, Any]]:
        """Recherche Tavily et retourne des résultats normalisés."""

        if not TAVILY_API_KEY:
            logger.error("❌ TAVILY_API_KEY absente")
            return []

        payload = {
            "api_key": TAVILY_API_KEY,
            "query": f"{query} (Madagascar OR Antananarivo)",
            "search_depth": "basic",
            "max_results": MAX_RESULTS_TAVILY,
            "include_raw_content": False,
            "include_images": False,
        }

        start = time.perf_counter()

        try:
            response = await retry_with_backoff(
                self._do_request,
                payload,
                max_retries=RETRY_MAX_ATTEMPTS,
                base_delay=RETRY_BASE_DELAY,
                retryable_exceptions=(httpx.TimeoutException, httpx.HTTPError),
                label="Tavily",
            )

            elapsed = time.perf_counter() - start
            logger.info("⏱️ Tavily : %.3fs", elapsed)

            if response.status_code != 200:
                logger.error(
                    "❌ Tavily HTTP %s : %s",
                    response.status_code,
                    response.text[:500],
                )
                return []

            data = response.json()
            raw_results = data.get("results", [])

            if not isinstance(raw_results, list):
                return []

            results = []
            for result in raw_results:
                if not isinstance(result, dict):
                    continue

                results.append({
                    **result,
                    "title": str(result.get("title", "")).strip(),
                    "url": normalize_url(result.get("url", "")),
                    "content": str(
                        result.get("content", "") or result.get("snippet", "")
                    ).strip(),
                })

            logger.info("📊 Tavily : %d résultats", len(results))
            return results

        except (httpx.TimeoutException, httpx.HTTPError) as exc:
            logger.error("❌ Tavily indisponible après retries : %s", exc)
            return []

        except Exception as exc:
            logger.exception("❌ Tavily : %s", exc)
            return []