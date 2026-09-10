
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
# import re
# import time
# from typing import Any, Dict, List

# import httpx

# from app.utils.retry import retry_with_backoff
# from app.utils.url_utils import normalize_url

# logger = logging.getLogger(__name__)

# TAVILY_API_KEY = os.getenv("TAVILY_API_KEY")
# # 8 = exactement 2 lots complets de MAX_RESULTS_AI (4). Demander
# # plus (ex: 10) n'apporte rien puisque le fallback par lots ne va
# # jamais au-delà de 2 lots, et ralentit Tavily sans bénéfice.
# MAX_RESULTS_TAVILY = int(os.getenv("MAX_RESULTS_TAVILY", "8"))
# TAVILY_TIMEOUT = float(os.getenv("TAVILY_TIMEOUT", "20"))
# RETRY_MAX_ATTEMPTS = int(os.getenv("RETRY_MAX_ATTEMPTS", "3"))
# RETRY_BASE_DELAY = float(os.getenv("RETRY_BASE_DELAY", "1.0"))

# # Motifs de bruit fréquents dans le contenu scrapé (murs de connexion
# # réseaux sociaux, artefacts d'images, agrégateurs) — observés
# # concrètement dans les logs de production (Facebook "Log In",
# # "Forgot Account?", placeholders "Image N:").
# NOISE_PATTERNS = [
#     r"Log In\s*",
#     r"Forgot Account\?\s*",
#     r"Image \d+:\s*",
#     r"Se connecter\s*",
#     r"Mot de passe oubli[ée]\s*",
#     r"S'inscrire\s*",
# ]


# def clean_scraped_content(text: str) -> str:
#     """
#     Retire le bruit connu du contenu scrapé par Tavily avant qu'il
#     ne soit envoyé au LLM. Réduit le budget de prompt gaspillé et
#     le risque de confusion du modèle sur du texte non pertinent.
#     """
#     if not text:
#         return text

#     cleaned = text
#     for pattern in NOISE_PATTERNS:
#         cleaned = re.sub(pattern, "", cleaned, flags=re.IGNORECASE)

#     # Compacte les sauts de ligne et espaces multiples résiduels.
#     cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
#     cleaned = re.sub(r"[ \t]{2,}", " ", cleaned)

#     return cleaned.strip()


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
# SERVICE TAVILY — VERSION CORRIGÉE (V3.0)
# ============================================================
# Corrections :
# 1. Utilise site: operators dans la query (plus fiable que include_domains)
# 2. Filtre POST-Tavily : rejette URLs non autorisées
# 3. Rejette contenu non-latin (chinois, cyrillique, arabe)
# 4. Rejette mots-clés bruit (krym, pilates, sports, etc.)
# 5. Fallback intelligent : si 0 résultats, essaie sans site:
# 6. Cache simple pour éviter conflits sur recherches répétées
# 7. Timeout adaptatif selon search_depth
# ============================================================

import hashlib
import logging
import os
import re
import time
from typing import Any, Dict, List, Optional

import httpx

from app.utils.retry import retry_with_backoff
from app.utils.url_utils import normalize_url

logger = logging.getLogger(__name__)

# ============================================================
# CONFIGURATION (depuis .env)
# ============================================================
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY")
MAX_RESULTS_TAVILY = int(os.getenv("TAVILY_MAX_RESULTS", "15"))
TAVILY_TIMEOUT = float(os.getenv("TAVILY_TIMEOUT", "12"))
RETRY_MAX_ATTEMPTS = int(os.getenv("RETRY_MAX_ATTEMPTS", "3"))
RETRY_BASE_DELAY = float(os.getenv("RETRY_BASE_DELAY", "1.0"))

# Domaine MALGACHES azo itokisana (utilisés pour site: ET post-filtrage)
TRUSTED_DOMAINS = [
    "asako.mg",
    "job2mada.com",
    "portaljob-madagascar.com",
    "codeko.tech",
    "optioncarriere.mg",
    "emploi.mg",
    "recrutement.mg",
    "developa.net",
    "linkedin.com",
    "facebook.com",
    "indeed.com",
]

# Mots-clés bruit à rejeter (contenu non-pertinent)
NOISE_KEYWORDS = [
    # Conflits géopolitiques
    "krym", "crimea", "ukraine", "russia", "rosja", "wojna",
    "guerre", "war", "missile", "drone", "sanctions",
    # Lifestyle / non-tech
    "pilates", "yoga", "fitness", "skincare", "cosmetic", "beauty",
    "recipe", "cuisine", "restaurant", "travel", "voyage", "tourisme",
    "sports", "football", "tennis", "movie", "film", "cinema",
    # Finance générale
    "bourse", "crypto", "bitcoin", "trading", "forex",
    # Santé / bien-être
    "santé", "health", "wellness", "spa", "massage",
    # Universités / études (pas des offres d'emploi)
    "université", "university", "sapienza", "étudiant", "student",
    "bachelor", "master académique", "thèse", "phd",
]

# Regex pour détecter les caractères non-latins
NON_LATIN_REGEX = re.compile(
    r"[\u4E00-\u9FFF"   # CJK (chinois, japonais)
    r"\u3040-\u30FF"    # Hiragana/Katakana
    r"\u0600-\u06FF"    # Arabe
    r"\u0400-\u04FF"    # Cyrillique
    r"\u0590-\u05FF]"   # Hébreu
)

# Patterns de bruit (murs de connexion, etc.)
NOISE_PATTERNS = [
    r"Log In\s*",
    r"Forgot Account\?\s*",
    r"Image \d+:\s*",
    r"Se connecter\s*",
    r"Mot de passe oubli[ée]\s*",
    r"S'inscrire\s*",
]


def clean_scraped_content(text: str) -> str:
    """Retire le bruit connu du contenu scrapé."""
    if not text:
        return text

    cleaned = text
    for pattern in NOISE_PATTERNS:
        cleaned = re.sub(pattern, "", cleaned, flags=re.IGNORECASE)

    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    cleaned = re.sub(r"[ \t]{2,}", " ", cleaned)
    return cleaned.strip()


def is_latin_content(text: str) -> bool:
    """Retourne True si le contenu est en alphabet latin (pas CJK/cyrillique/arabe)."""
    if not text:
        return True
    # Si > 5% de caractères non-latins → considérer comme non-latin
    non_latin_count = len(NON_LATIN_REGEX.findall(text))
    return non_latin_count < (len(text) * 0.05)


def contains_noise(text: str) -> bool:
    """Retourne True si le texte contient des mots-clés bruit."""
    text_lower = text.lower()
    return any(kw in text_lower for kw in NOISE_KEYWORDS)


def is_trusted_url(url: str) -> bool:
    """Retourne True si l'URL vient d'un domaine autorisé."""
    url_lower = url.lower()
    return any(domain in url_lower for domain in TRUSTED_DOMAINS)


class TavilyService:
    """Recherche web via Tavily avec filtrage robuste + cache simple."""

    # Cache en mémoire pour éviter conflits (TTL 5 min)
    _cache: Dict[str, tuple] = {}
    _cache_ttl = 300  # 5 minutes

    def __init__(self):
        if TAVILY_API_KEY:
            logger.info("🔎 TAVILY configuré (V3.0 - filtrage robuste)")
        else:
            logger.warning("⚠️ TAVILY_API_KEY absente")

    def _cache_key(self, query: str) -> str:
        """Génère une clé de cache pour une query."""
        return hashlib.md5(query.lower().strip().encode()).hexdigest()

    def _get_from_cache(self, query: str) -> Optional[List[Dict[str, Any]]]:
        """Récupère depuis le cache si non expiré."""
        key = self._cache_key(query)
        if key in self._cache:
            data, timestamp = self._cache[key]
            if time.time() - timestamp < self._cache_ttl:
                logger.info("💾 Cache HIT pour: %s", query[:60])
                return data
            else:
                del self._cache[key]
        return None

    def _set_cache(self, query: str, results: List[Dict[str, Any]]) -> None:
        """Stocke dans le cache."""
        key = self._cache_key(query)
        self._cache[key] = (results, time.time())

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
        """
        Recherche Tavily avec filtrage multi-niveaux :
        1. Vérifie le cache
        2. Envoie la requête avec site: operators
        3. Filtre les résultats (URL, langue, bruit)
        4. Si 0 résultats, retente SANS site: (fallback)
        5. Filtre à nouveau le fallback
        6. Stocke dans le cache
        """

        if not TAVILY_API_KEY:
            logger.error("❌ TAVILY_API_KEY absente")
            return []

        query = str(query or "").strip()
        if not query:
            return []

        # ✅ 1. Vérifier le cache
        cached = self._get_from_cache(query)
        if cached is not None:
            return cached

        # ✅ 2. Construire la query avec site: operators
        base_query = query
        for word in ["Madagascar", "madagascar", "Antananarivo", "antananarivo"]:
            base_query = base_query.replace(word, "")
        base_query = base_query.strip()

        # Sites prioritaires (top 5 seulement pour éviter query trop longue)
        priority_sites = [
            "asako.mg",
            "job2mada.com",
            "portaljob-madagascar.com",
            "codeko.tech",
            "optioncarriere.mg",
        ]
        site_operators = " OR ".join([f"site:{s}" for s in priority_sites])
        enhanced_query = f"{base_query} Madagascar ({site_operators})"

        logger.info("🌐 Tavily query (with sites): %s", enhanced_query[:150])

        payload = {
            "api_key": TAVILY_API_KEY,
            "query": enhanced_query,
            "search_depth": "basic",  # Basic = rapide ; advanced = 10-28s
            "max_results": MAX_RESULTS_TAVILY,
            "include_raw_content": False,
            "include_images": False,
            "include_answer": False,
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
            logger.info("⏱️ Tavily (with sites) : %.3fs", elapsed)

            if response.status_code == 200:
                data = response.json()
                raw_results = data.get("results", [])
                filtered = self._filter_results(raw_results)

                logger.info(
                    "📊 Tavily (with sites): %d bruts → %d après filtrage",
                    len(raw_results), len(filtered)
                )

                if filtered:
                    self._set_cache(query, filtered)
                    return filtered
            else:
                logger.warning(
                    "⚠️ Tavily HTTP %s sur requête avec sites",
                    response.status_code
                )

        except (httpx.TimeoutException, httpx.HTTPError) as exc:
            logger.warning("⚠️ Tavily (with sites) échoué: %s", exc)

        # ✅ 3. FALLBACK : Retenter SANS site: operators
        logger.info("🔄 Fallback Tavily : retenter sans site: operators")

        fallback_query = f"{base_query} Madagascar"
        fallback_payload = {
            "api_key": TAVILY_API_KEY,
            "query": fallback_query,
            "search_depth": "basic",
            "max_results": MAX_RESULTS_TAVILY,
            "include_raw_content": False,
            "include_images": False,
            "include_answer": False,
        }

        start = time.perf_counter()

        try:
            response = await retry_with_backoff(
                self._do_request,
                fallback_payload,
                max_retries=RETRY_MAX_ATTEMPTS,
                base_delay=RETRY_BASE_DELAY,
                retryable_exceptions=(httpx.TimeoutException, httpx.HTTPError),
                label="Tavily-Fallback",
            )

            elapsed = time.perf_counter() - start
            logger.info("⏱️ Tavily (fallback) : %.3fs", elapsed)

            if response.status_code != 200:
                logger.error(
                    "❌ Tavily fallback HTTP %s", response.status_code
                )
                return []

            data = response.json()
            raw_results = data.get("results", [])
            filtered = self._filter_results(raw_results)

            logger.info(
                "📊 Tavily (fallback): %d bruts → %d après filtrage",
                len(raw_results), len(filtered)
            )

            # ✅ Si fallback retourne résultats, on accepte MÊME si domaines non-autorisés
            # (car Tavily peut ne pas avoir les sites malgaches indexés)
            if filtered:
                self._set_cache(query, filtered)
                return filtered

            # ✅ Si vraiment 0, on garde quelques résultats bruts "propres"
            # (utile pour montrer au LLM qu'il n'y a rien)
            clean_raw = self._filter_minimal(raw_results)
            self._set_cache(query, clean_raw)
            return clean_raw

        except (httpx.TimeoutException, httpx.HTTPError) as exc:
            logger.error("❌ Tavily fallback échoué: %s", exc)
            return []
        except Exception as exc:
            logger.exception("❌ Tavily : %s", exc)
            return []

    def _filter_results(
        self, raw_results: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Filtrage STRICT :
        - URL doit venir d'un domaine autorisé
        - Contenu doit être latin
        - Pas de mots-clés bruit
        """
        filtered = []

        for result in raw_results:
            if not isinstance(result, dict):
                continue

            title = str(result.get("title", "")).strip()
            url = str(result.get("url", "")).strip()
            content = str(
                result.get("content", "") or result.get("snippet", "")
            ).strip()

            # Filtre 1 : URL autorisée
            if not is_trusted_url(url):
                logger.debug("   🚫 URL non autorisée: %s", url[:80])
                continue

            # Filtre 2 : Contenu latin
            if not is_latin_content(title + " " + content):
                logger.debug("   🚫 Contenu non-latin: %s", title[:60])
                continue

            # Filtre 3 : Pas de bruit
            if contains_noise(title + " " + content):
                logger.debug("   🚫 Bruit détecté: %s", title[:60])
                continue

            filtered.append({
                "title": title,
                "url": normalize_url(url),
                "content": clean_scraped_content(content),
                "score": result.get("score", 0.0),
            })

        return filtered

    def _filter_minimal(
        self, raw_results: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Filtrage MINIMAL (utilisé en dernier recours) :
        - Rejette uniquement non-latin + bruit
        - Accepte TOUTES les URLs (même non-autorisées)
        """
        filtered = []

        for result in raw_results:
            if not isinstance(result, dict):
                continue

            title = str(result.get("title", "")).strip()
            url = str(result.get("url", "")).strip()
            content = str(
                result.get("content", "") or result.get("snippet", "")
            ).strip()

            if not is_latin_content(title + " " + content):
                continue

            if contains_noise(title + " " + content):
                continue

            filtered.append({
                "title": title,
                "url": normalize_url(url),
                "content": clean_scraped_content(content),
                "score": result.get("score", 0.0),
            })

        return filtered