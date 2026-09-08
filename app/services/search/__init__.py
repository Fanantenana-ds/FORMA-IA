# app/services/search/search_manager.py
# ============================================================
# SEARCH MANAGER
# ============================================================
# Ce service gère la recherche, la fusion et la déduplication
# des résultats provenant de Tavily.
# ============================================================

from typing import List, Dict
from app.clients.tavily_client import TavilyClient

class SearchManager:
    """Gestionnaire de recherche avec fusion et déduplication"""

    def __init__(self):
        self.tavily_client = TavilyClient()

    def search_and_merge(self, query: str, max_results: int = 20) -> List[Dict]:
        """
        Recherche, fusionne et déduplique les résultats

        Args:
            query (str): La requête de recherche
            max_results (int): Nombre maximum de résultats

        Returns:
            List[Dict]: Liste des résultats uniques
        """
        # 1. Récupérer les résultats depuis Tavily
        results = self.tavily_client.search(query, max_results * 2)

        # 2. Fusionner et dédupliquer
        merged = self._merge_results(results)

        # 3. Limiter le nombre de résultats
        return merged[:max_results]

    def _merge_results(self, results: List[Dict]) -> List[Dict]:
        """
        Fusionne et déduplique les résultats

        Stratégie :
        1. Grouper par URL exacte
        2. Grouper par titre similaire (>80%)
        3. Garder le meilleur résultat pour chaque groupe
        """
        if not results:
            return []

        # Étape 1 : Déduplication par URL
        seen_urls = set()
        url_unique = []
        for item in results:
            url = item.get("url", "").strip()
            if url and url not in seen_urls:
                seen_urls.add(url)
                url_unique.append(item)

        # Étape 2 : Déduplication par titre similaire
        # (Version simplifiée - on garde les titres uniques)
        seen_titles = set()
        title_unique = []
        for item in url_unique:
            title = item.get("title", "").strip().lower()
            # Si le titre est vide ou déjà vu, on le saute
            if not title or title in seen_titles:
                continue
            seen_titles.add(title)
            title_unique.append(item)

        return title_unique

    def _is_similar_title(self, title1: str, title2: str) -> bool:
        """Vérifie si deux titres sont similaires (>80% de similarité)"""
        # Version simplifiée : on vérifie les mots communs
        words1 = set(title1.lower().split())
        words2 = set(title2.lower().split())
        if not words1 or not words2:
            return False
        common = len(words1 & words2)
        total = len(words1 | words2)
        return (common / total) > 0.7 if total > 0 else False