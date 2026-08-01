# app/clients/tavily_client.py
# ============================================================
# CLIENT TAVILY API
# ============================================================
# Ce fichier gère les appels à l'API Tavily pour la recherche
# d'opportunités commerciales.
# ============================================================

import os
import requests
from typing import List, Dict, Optional
from dotenv import load_dotenv

load_dotenv()

class TavilyClient:
    """Client pour l'API Tavily (recherche d'opportunités)"""

    def __init__(self, api_key: Optional[str] = None):
        """Initialise le client avec la clé API depuis .env"""
        self.api_key = api_key or os.getenv("TAVILY_API_KEY")
        if not self.api_key:
            raise ValueError("TAVILY_API_KEY non trouvée dans .env")
        
        self.base_url = "https://api.tavily.com/search"
        self.timeout = 10  # secondes

    def search(self, query: str, max_results: int = 20) -> List[Dict]:
        """
        Recherche des résultats via Tavily API

        Args:
            query (str): La requête de recherche
            max_results (int): Nombre maximum de résultats (par défaut 20)

        Returns:
            List[Dict]: Liste des résultats avec url, title, snippet, source, date

        Raises:
            Exception: En cas d'erreur API
        """
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        payload = {
            "query": query,
            "max_results": max_results,
            "include_answer": False,
            "include_raw_content": False
        }

        try:
            response = requests.post(
                self.base_url,
                json=payload,
                headers=headers,
                timeout=self.timeout
            )
            response.raise_for_status()
            data = response.json()

            results = []
            for item in data.get("results", []):
                results.append({
                    "url": item.get("url", ""),
                    "title": item.get("title", "Sans titre"),
                    "snippet": item.get("content", ""),
                    "source": item.get("source", "tavily"),
                    "date": item.get("published_date", None)
                })

            return results

        except requests.exceptions.Timeout:
            raise Exception("Timeout lors de l'appel à Tavily")
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 429:
                raise Exception("Rate limit atteint (Tavily)")
            raise Exception(f"Erreur HTTP Tavily: {e}")
        except Exception as e:
            raise Exception(f"Erreur Tavily: {str(e)}")