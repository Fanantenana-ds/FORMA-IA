# ============================================================
# FORMA-IA — SEARCH MANAGER (VERSION MADAGASCAR PRIORITAIRE)
# ============================================================
# Ce fichier gère la recherche, la fusion et la déduplication
# des résultats provenant de Tavily.
# ============================================================

import os
import logging
from typing import List, Dict, Optional
from app.clients.tavily_client import TavilyClient

logger = logging.getLogger(__name__)

class SearchManager:
    """Gestionnaire de recherche avec fusion et déduplication"""

    def __init__(self):
        """Initialise le SearchManager avec le client Tavily"""
        self.tavily_client = TavilyClient()

    def search_and_merge(self, query: str, max_results: int = 20) -> List[Dict]:
        """
        Recherche, fusionne et déduplique les résultats
        PRIORITÉ : Madagascar d'abord, puis remote international

        Args:
            query (str): La requête de recherche
            max_results (int): Nombre maximum de résultats

        Returns:
            List[Dict]: Liste des résultats uniques
        """
        try:
            # ✅ CONSTRUCTION DE LA REQUÊTE CIBLÉE
            # Priorité 1 : Madagascar (sites .mg, Antananarivo, Asako, PortailJob)
            # Priorité 2 : Remote international compatible Madagascar
            
            modified_query = self._build_madagascar_query(query)
            logger.info(f"🔍 Requête Tavily modifiée: {modified_query}")
            
            results = self.tavily_client.search(modified_query, max_results * 2)
            logger.info(f"📊 {len(results)} résultats trouvés")

            # 2. Fusionner et dédupliquer
            merged = self._merge_results(results)

            # 3. Limiter le nombre de résultats
            final_results = merged[:max_results]
            logger.info(f"✅ {len(final_results)} résultats uniques après déduplication")
            return final_results

        except Exception as e:
            logger.error(f"❌ Erreur lors de la recherche: {e}")
            return []

    def _build_madagascar_query(self, query: str) -> str:
        """
        Construit une requête ciblant Madagascar en priorité
        """
        # Mots-clés Madagascar
        mg_keywords = [
            "Madagascar",
            "Antananarivo",
            "site:.mg",
            "Asako.mg",
            "PortailJob.mg",
            "ARMP Madagascar",
            "emploi Madagascar",
            "recrutement Madagascar",
            "offre Madagascar"
        ]
        
        # Si la requête contient déjà "Madagascar", on l'utilise directement
        if "Madagascar" in query or "Antananarivo" in query:
            return query
        
        # Pour les recherches d'emploi
        if any(word in query.lower() for word in ["emploi", "travail", "poste", "recrutement", "stage"]):
            return f"{query} (Madagascar OR Antananarivo OR site:.mg OR Asako.mg OR PortailJob.mg) OR ({query} remote Madagascar)"
        
        # Pour les recherches générales
        return f"{query} (Madagascar OR Antananarivo OR site:.mg) OR ({query} remote Madagascar)"

    def _merge_results(self, results: List[Dict]) -> List[Dict]:
        """
        Fusionne et déduplique les résultats
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

        # Étape 2 : Déduplication par titre
        seen_titles = set()
        title_unique = []
        for item in url_unique:
            title = item.get("title", "").strip().lower()
            if not title or title in seen_titles:
                continue
            seen_titles.add(title)
            title_unique.append(item)

        # Étape 3 : Prioriser les sources malgaches
        mg_sources = [".mg", "asako", "portailjob", "madagascar", "antananarivo"]
        priority_results = []
        other_results = []
        
        for item in title_unique:
            url = item.get("url", "").lower()
            title = item.get("title", "").lower()
            snippet = item.get("snippet", "").lower()
            
            # Vérifier si c'est une source malgache
            is_mg = any(
                src in url or src in title or src in snippet
                for src in mg_sources
            )
            
            if is_mg:
                item["is_madagascar"] = True
                priority_results.append(item)
            else:
                item["is_madagascar"] = False
                other_results.append(item)
        
        # Retourner les résultats malgaches en premier
        return priority_results + other_results

    def _is_similar_title(self, title1: str, title2: str) -> bool:
        """Vérifie si deux titres sont similaires"""
        if not title1 or not title2:
            return False
        words1 = set(title1.lower().split())
        words2 = set(title2.lower().split())
        if not words1 or not words2:
            return False
        common = len(words1 & words2)
        total = len(words1 | words2)
        return (common / total) > 0.7 if total > 0 else False