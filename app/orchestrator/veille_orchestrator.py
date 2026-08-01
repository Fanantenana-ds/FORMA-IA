# ============================================================
# ORCHESTRATEUR M1 — VEILLE MARCHÉ
# ============================================================

import os
import json
import yaml
import logging
from typing import Dict, List, Any
from anthropic import Anthropic
from dotenv import load_dotenv

from app.services.search.search_manager import SearchManager
from app.services.validation.validator import Validator

load_dotenv()
logger = logging.getLogger(__name__)

class VeilleOrchestrator:
    """Orchestrateur pour le module M1 (Veille Marché)"""

    def __init__(self):
        self.client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
        self.model = os.getenv("CLAUDE_MODEL", "claude-3-5-sonnet-20241022")
        self.search_manager = SearchManager()
        self.validator = Validator()

        # Charger les prompts
        self.system_prompt = self._load_prompt("app/prompts/m1/veille.yaml")

    def _load_prompt(self, path: str) -> str:
        """Charge le prompt depuis un fichier YAML"""
        try:
            with open(path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)

            prompt = (
                config.get("role", "") + "\n\n" +
                config.get("task", "") + "\n\n" +
                config.get("format", "") + "\n\n" +
                config.get("context", "") + "\n\n" +
                "EXEMPLES :\n" + config.get("examples", "") + "\n\n" +
                config.get("security", "")
            )
            logger.info(f"✅ Prompt chargé: {path}")
            return prompt
        except Exception as e:
            logger.error(f"❌ Erreur chargement prompt {path}: {e}")
            return ""

    def analyser_opportunites(self, query: str) -> Dict[str, Any]:
        """
        Analyse les opportunités pour une requête donnée

        Args:
            query (str): La requête de recherche

        Returns:
            Dict: Résultats structurés
        """
        try:
            # 1. Rechercher les opportunités
            results = self.search_manager.search_and_merge(query)

            if not results:
                return {
                    "success": True,
                    "data": {
                        "opportunities": [],
                        "total": 0,
                        "message": "Aucun résultat trouvé"
                    }
                }

            # 2. Préparer les données pour Claude
            input_text = self._format_results_for_claude(results)

            # 3. Appeler Claude avec Tool Calling
            response = self._call_claude(input_text)

            # 4. Parser la réponse
            parsed = self._parse_response(response)

            # 5. Valider les données
            validated = self.validator.validate_batch(parsed.get("opportunities", []))

            return {
                "success": True,
                "data": {
                    "opportunities": validated,
                    "total": len(validated),
                    "validated_count": len([o for o in validated if o.get("status") == "validated"])
                }
            }

        except Exception as e:
            logger.error(f"❌ Erreur: {e}")
            return {
                "success": False,
                "data": {},
                "error": str(e)
            }

    def _format_results_for_claude(self, results: List[Dict]) -> str:
        """Formate les résultats pour Claude"""
        formatted = "Voici une liste d'opportunités à analyser :\n\n"
        for i, item in enumerate(results, 1):
            formatted += f"Opportunité {i} :\n"
            formatted += f"Titre : {item.get('title', 'Sans titre')}\n"
            formatted += f"Source : {item.get('source', 'Non précisé')}\n"
            formatted += f"URL : {item.get('url', 'Non précisé')}\n"
            formatted += f"Extrait : {item.get('snippet', 'Non précisé')[:300]}...\n\n"
        return formatted

    def _call_claude(self, input_text: str) -> Dict:
        """Appelle Claude avec Tool Calling"""
        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=4096,
                temperature=float(os.getenv("CLAUDE_TEMPERATURE", 0.1)),
                system=self.system_prompt,
                tools=[{
                    "name": "classifier",
                    "description": "Classifie et analyse les opportunités commerciales",
                    "input_schema": {
                        "type": "object",
                        "properties": {
                            "opportunities": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "title": {"type": "string"},
                                        "source": {"type": "string"},
                                        "url": {"type": "string"},
                                        "budget": {"type": "string"},
                                        "deadline": {"type": "string"},
                                        "organizer": {"type": "string"},
                                        "domain": {
                                            "type": "string",
                                            "enum": ["ia", "devops", "data", "developpement", "bureautique", "autre"]
                                        },
                                        "summary": {"type": "string"},
                                        "score": {"type": "integer", "minimum": 0, "maximum": 100},
                                        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                                        "reason": {"type": "string"}
                                    },
                                    "required": ["title", "source", "domain", "summary", "score", "confidence"]
                                }
                            },
                            "total": {"type": "integer"}
                        },
                        "required": ["opportunities", "total"]
                    }
                }],
                messages=[{"role": "user", "content": input_text}]
            )

            # Extraire le JSON de la réponse
            content = response.content[0].text
            return self._extract_json(content)

        except Exception as e:
            logger.error(f"❌ Erreur Claude: {e}")
            return {"opportunities": [], "total": 0}

    def _extract_json(self, text: str) -> Dict:
        """Extrait le JSON de la réponse de Claude"""
        import re
        try:
            match = re.search(r'```json\s*(\{.*?\})\s*```', text, re.DOTALL)
            if match:
                return json.loads(match.group(1))
            match = re.search(r'(\{.*\})', text, re.DOTALL)
            if match:
                return json.loads(match.group(1))
            return {"opportunities": [], "total": 0}
        except json.JSONDecodeError:
            logger.error("❌ Erreur parsing JSON")
            return {"opportunities": [], "total": 0}

    def _parse_response(self, response: Dict) -> Dict:
        """Parse la réponse de Claude"""
        return response