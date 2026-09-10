# # # # app/clients/tavily_client.py
# # ============================================================
# # FORMA-IA — TAVILY CLIENT (AVEC FALLBACK)
# # ============================================================

# import os
# import logging
# import requests
# from typing import List, Dict, Optional
# from dotenv import load_dotenv

# load_dotenv()
# logger = logging.getLogger(__name__)

# class TavilyClient:
#     """Client pour l'API Tavily avec fallback"""

#     def __init__(self, api_key: Optional[str] = None):
#         self.api_key = api_key or os.getenv("TAVILY_API_KEY")
#         if not self.api_key:
#             logger.warning("⚠️ TAVILY_API_KEY non trouvée")
        
#         self.base_url = "https://api.tavily.com/search"
#         self.timeout = 15

#     def search(self, query: str, max_results: int = 20) -> List[Dict]:
#         """
#         Recherche des résultats via Tavily
#         """
#         if not self.api_key:
#             logger.warning("⚠️ Aucune clé Tavily, retour des résultats mock")
#             return self._mock_results(query)

#         try:
#             headers = {
#                 "Authorization": f"Bearer {self.api_key}",
#                 "Content-Type": "application/json"
#             }
#             payload = {
#                 "query": query,
#                 "max_results": max_results,
#                 "search_depth": "advanced",
#                 "include_answer": False,
#                 "include_raw_content": True,
#                 "include_images": False
#             }

#             logger.info(f"🌐 Envoi requête Tavily: {query[:100]}...")
            
#             response = requests.post(
#                 self.base_url,
#                 json=payload,
#                 headers=headers,
#                 timeout=self.timeout
#             )
#             response.raise_for_status()
#             data = response.json()

#             results = []
#             for item in data.get("results", []):
#                 results.append({
#                     "url": item.get("url", ""),
#                     "title": item.get("title", "Sans titre"),
#                     "snippet": item.get("content", ""),
#                     "source": item.get("source", "tavily"),
#                     "date": item.get("published_date", None),
#                     "raw_content": item.get("raw_content", "")
#                 })
            
#             logger.info(f"✅ Tavily: {len(results)} résultats")
#             return results

#         except requests.exceptions.Timeout:
#             logger.error("❌ Timeout Tavily")
#             return self._mock_results(query)
#         except requests.exceptions.ConnectionError:
#             logger.error("❌ Erreur de connexion Tavily")
#             return self._mock_results(query)
#         except requests.exceptions.HTTPError as e:
#             logger.error(f"❌ HTTP Error Tavily: {e}")
#             return self._mock_results(query)
#         except Exception as e:
#             logger.error(f"❌ Erreur Tavily: {e}")
#             return self._mock_results(query)

#     def _mock_results(self, query: str) -> List[Dict]:
#         """
#         Retourne des résultats simulés pour les tests
#         """
#         logger.info("📊 Utilisation des données mock (pas de Tavily)")
        
#         mock_data = [
#             {
#                 "url": "https://example.com/offre1",
#                 "title": f"Opportunité IA - {query[:30]}",
#                 "snippet": "Appel d'offres pour une formation en intelligence artificielle...",
#                 "source": "mock",
#                 "date": "2026-08-13"
#             },
#             {
#                 "url": "https://example.com/offre2",
#                 "title": f"Poste Data Scientist - {query[:30]}",
#                 "snippet": "Recherche d'un data scientist pour analyser les données...",
#                 "source": "mock",
#                 "date": "2026-08-12"
#             },
#             {
#                 "url": "https://example.com/offre3",
#                 "title": f"DevOps Cloud - {query[:30]}",
#                 "snippet": "Migration vers le cloud avec Kubernetes...",
#                 "source": "mock",
#                 "date": "2026-08-11"
#             }
#         ]
#         return mock_data




# app/clients/tavily_client.py
# ============================================================
# FORMA-IA — TAVILY CLIENT (ASYNC + FILTERING)
# ============================================================

import os
import logging
from typing import List, Dict, Optional

import httpx
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

# ✅ Domaine azo itokisana any Madagascar
TRUSTED_DOMAINS = [
    "asako.mg",
    "job2mada.com",
    "codeko.tech",
    "optioncarriere.mg",
    "madagascar-internet.com",
    "developa.net",
    "linkedin.com",
    "indeed.com",
    "emploimadagascar.com",
    "recrutement.mg"
]

# ❌ Domaine tsy ilaina
EXCLUDED_DOMAINS = [
    "wikipedia.org",
    "youtube.com",
    "facebook.com",
    "instagram.com",
    "twitter.com",
    "amazon.com",
    "ebay.com",
    "skincare.com",
    "rescue-spa.com"
]

# ❌ Teny tsy ilaina
EXCLUDED_KEYWORDS = [
    "skincare", "lotion", "cosmetic", "beauty", "makeup",
    "film", "movie", "trailer", "cinema", "hollywood",
    "zoo", "lemur", "wildlife", "animal",
    "bitcoin", "crypto", "blockchain",
    "unicef", "survey", "mics",
    "travel", "safari", "tourist"
]


class TavilyClient:
    """Client Tavily async avec filtrage de domaine et fallback."""

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("TAVILY_API_KEY")
        if not self.api_key:
            raise ValueError("⚠️ TAVILY_API_KEY absente — le client ne peut pas fonctionner")

        self.base_url = "https://api.tavily.com/search"
        self.max_results = int(os.getenv("TAVILY_MAX_RESULTS", "15"))
        self.timeout = float(os.getenv("TAVILY_TIMEOUT", "10"))

    async def search(self, query: str, max_results: Optional[int] = None) -> List[Dict]:
        """
        Fikarohana Tavily miaraka amin'ny filtrage.
        Retourne TOUJOURS une liste (jamais None), même vide.
        """
        if not self.api_key:
            logger.error("❌ TAVILY_API_KEY manquante")
            return []

        max_results = max_results or self.max_results

        # ✅ Fanatsarana ny query raha tsy misy site:
        if "site:" not in query.lower():
            enhanced_query = (
                f"{query} "
                f"(site:asako.mg OR site:job2mada.com OR site:codeko.tech)"
            )
        else:
            enhanced_query = query

        payload = {
            "api_key": self.api_key,  # ✅ ZAVA-DEHIBE: amin'ny body fa tsy header
            "query": enhanced_query,
            "search_depth": "basic",  # ✅ Haingana (advanced = 5-10s)
            "max_results": max_results,
            "include_answer": False,
            "include_raw_content": False,
            "include_images": False,
            "include_domains": TRUSTED_DOMAINS,   # ✅ ZAVA-DEHIBE
            "exclude_domains": EXCLUDED_DOMAINS,  # ✅ ZAVA-DEHIBE
        }

        logger.info(f"🌐 Tavily query: {enhanced_query[:100]}...")

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(self.base_url, json=payload)
                response.raise_for_status()
                data = response.json()

            raw_results = data.get("results", [])
            logger.info(f"📊 Tavily: {len(raw_results)} résultats bruts")

            # ✅ Filtrage sy normalisation
            filtered = self._filter_and_normalize(raw_results)
            logger.info(f"✅ Tavily: {len(filtered)} résultats après filtrage")

            return filtered

        except httpx.TimeoutException:
            logger.error("❌ Tavily: Timeout")
            return []
        except httpx.HTTPStatusError as e:
            logger.error(f"❌ Tavily: HTTP {e.response.status_code} - {e}")
            return []
        except Exception as e:
            logger.error(f"❌ Tavily: {e}")
            return []

    def _filter_and_normalize(self, results: List[Dict]) -> List[Dict]:
        """Manadio sy mandamina ny valiny Tavily."""
        normalized = []

        for item in results:
            url = str(item.get("url", "")).lower()
            title = str(item.get("title", "")).lower()
            content = str(item.get("content", "")).lower()
            combined = f"{title} {content}"

            # ❌ Esorina raha misy teny voarara
            if any(kw in combined for kw in EXCLUDED_KEYWORDS):
                logger.info(f"   🚫 Exclu (keyword): {title[:60]}")
                continue

            # ❌ Esorina raha avy amin'ny domaine voarara
            if any(dom in url for dom in EXCLUDED_DOMAINS):
                logger.info(f"   🚫 Exclu (domain): {title[:60]}")
                continue

            # ✅ Tazonina ny valiny mifandraika amin'ny asa
            normalized.append({
                "url": item.get("url", ""),
                "title": item.get("title", "Sans titre"),
                "content": item.get("content", ""),
                "score": item.get("score", 0.0),
            })

        return normalized