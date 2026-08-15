# ============================================================
# ORCHESTRATEUR M1 — VEILLE MARCHÉ (AVEC GROQ VIA OPENAI)
# ============================================================
# Version : V1.0
# Date : 13 Août 2026
# ============================================================

import os
import json
import yaml
import logging
from typing import Dict, List, Any
from openai import OpenAI
from dotenv import load_dotenv

from app.services.search.search_manager import SearchManager
from app.services.validation.validator import Validator

load_dotenv()
logger = logging.getLogger(__name__)


class VeilleOrchestrator:
    """Orchestrateur pour le module M1 avec Groq (via OpenAI)"""

    def __init__(self):
        """Initialise l'orchestrateur avec Groq via OpenAI"""
        # --- Configuration de Groq ---
        api_key = os.getenv("GROQ_API_KEY")
        if not api_key:
            raise ValueError("❌ GROQ_API_KEY non trouvée dans .env")
        
        # Mampiasa OpenAI client miaraka amin'ny base_url Groq
        self.client = OpenAI(
            api_key=api_key,
            base_url="https://api.groq.com/openai/v1"
        )
        self.model = "llama-3.3-70b-versatile"  # ou "mixtral-8x7b-32768"
        
        self.search_manager = SearchManager()
        self.validator = Validator()

        # Charger les prompts
        self.system_prompt = self._load_prompt("app/prompts/m1/veille.yaml")
        logger.info(f"✅ Orchestrateur M1 initialisé avec Groq ({self.model}) via OpenAI")

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

            # 2. Préparer les données pour Groq
            input_text = self._format_results_for_groq(results)

            # 3. Appeler Groq (via OpenAI)
            response = self._call_groq(input_text)

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

    def _format_results_for_groq(self, results: List[Dict]) -> str:
        """Formate les résultats pour Groq"""
        formatted = "Voici une liste d'opportunités à analyser :\n\n"
        for i, item in enumerate(results, 1):
            formatted += f"Opportunité {i} :\n"
            formatted += f"Titre : {item.get('title', 'Sans titre')}\n"
            formatted += f"Source : {item.get('source', 'Non précisé')}\n"
            formatted += f"URL : {item.get('url', 'Non précisé')}\n"
            formatted += f"Extrait : {item.get('snippet', 'Non précisé')[:300]}...\n\n"
        return formatted

    def _call_groq(self, input_text: str) -> str:
        """Appelle Groq via OpenAI client"""
        try:
            # Construire le prompt complet
            full_prompt = self.system_prompt + "\n\n" + input_text + "\n\n" + """
            ⚠️ INSTRUCTION CRUCIALE :
            Tu dois répondre UNIQUEMENT au format JSON suivant, SANS aucun autre texte :

            {
              "opportunities": [
                {
                  "title": "Titre de l'opportunité",
                  "source": "Organisation émettrice",
                  "url": "URL ou null",
                  "budget": "Budget en Ariary ou 'Non précisé'",
                  "deadline": "Date au format YYYY-MM-DD ou null",
                  "organizer": "Organisme qui publie",
                  "domain": "ia|devops|data|developpement|bureautique|autre",
                  "summary": "Résumé en 3-4 phrases",
                  "score": 85,
                  "confidence": 0.92,
                  "reason": "Raison du score"
                }
              ],
              "total": 20
            }

            ⚠️ Réponds UNIQUEMENT le JSON. Pas de commentaire, pas d'explication.
            """

            # Appeler Groq via OpenAI
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "Tu es un expert en analyse d'appels d'offres. Tu réponds UNIQUEMENT en JSON."},
                    {"role": "user", "content": full_prompt}
                ],
                temperature=0.1,
                max_tokens=2048,
                response_format={"type": "json_object"}
            )

            # Extraire le contenu
            content = response.choices[0].message.content
            logger.info(f"✅ Réponse Groq reçue ({len(content)} caractères)")

            return content

        except Exception as e:
            logger.error(f"❌ Erreur Groq: {e}")
            return '{"opportunities": [], "total": 0}'

    def _parse_response(self, response: str) -> Dict:
        """Parse la réponse JSON"""
        try:
            cleaned = response.strip()
            return json.loads(cleaned)
        except json.JSONDecodeError as e:
            logger.error(f"❌ Erreur parsing JSON: {e}")
            return {"opportunities": [], "total": 0}






# # ============================================================
# # ORCHESTRATEUR M1 — VEILLE MARCHÉ
# # ============================================================

# import os
# import json
# import yaml
# import logging
# from typing import Dict, List, Any
# from anthropic import Anthropic
# from dotenv import load_dotenv

# from app.services.search.search_manager import SearchManager
# from app.services.validation.validator import Validator

# load_dotenv()
# logger = logging.getLogger(__name__)

# class VeilleOrchestrator:
#     """Orchestrateur pour le module M1 (Veille Marché)"""

#     def __init__(self):
#         self.client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
#         self.model = os.getenv("CLAUDE_MODEL", "claude-3-5-sonnet-20241022")
#         self.search_manager = SearchManager()
#         self.validator = Validator()

#         # Charger les prompts
#         self.system_prompt = self._load_prompt("app/prompts/m1/veille.yaml")

#     def _load_prompt(self, path: str) -> str:
#         """Charge le prompt depuis un fichier YAML"""
#         try:
#             with open(path, 'r', encoding='utf-8') as f:
#                 config = yaml.safe_load(f)

#             prompt = (
#                 config.get("role", "") + "\n\n" +
#                 config.get("task", "") + "\n\n" +
#                 config.get("format", "") + "\n\n" +
#                 config.get("context", "") + "\n\n" +
#                 "EXEMPLES :\n" + config.get("examples", "") + "\n\n" +
#                 config.get("security", "")
#             )
#             logger.info(f"✅ Prompt chargé: {path}")
#             return prompt
#         except Exception as e:
#             logger.error(f"❌ Erreur chargement prompt {path}: {e}")
#             return ""

#     def analyser_opportunites(self, query: str) -> Dict[str, Any]:
#         """
#         Analyse les opportunités pour une requête donnée

#         Args:
#             query (str): La requête de recherche

#         Returns:
#             Dict: Résultats structurés
#         """
#         try:
#             # 1. Rechercher les opportunités
#             results = self.search_manager.search_and_merge(query)

#             if not results:
#                 return {
#                     "success": True,
#                     "data": {
#                         "opportunities": [],
#                         "total": 0,
#                         "message": "Aucun résultat trouvé"
#                     }
#                 }

#             # 2. Préparer les données pour Claude
#             input_text = self._format_results_for_claude(results)

#             # 3. Appeler Claude avec Tool Calling
#             response = self._call_claude(input_text)

#             # 4. Parser la réponse
#             parsed = self._parse_response(response)

#             # 5. Valider les données
#             validated = self.validator.validate_batch(parsed.get("opportunities", []))

#             return {
#                 "success": True,
#                 "data": {
#                     "opportunities": validated,
#                     "total": len(validated),
#                     "validated_count": len([o for o in validated if o.get("status") == "validated"])
#                 }
#             }

#         except Exception as e:
#             logger.error(f"❌ Erreur: {e}")
#             return {
#                 "success": False,
#                 "data": {},
#                 "error": str(e)
#             }

#     def _format_results_for_claude(self, results: List[Dict]) -> str:
#         """Formate les résultats pour Claude"""
#         formatted = "Voici une liste d'opportunités à analyser :\n\n"
#         for i, item in enumerate(results, 1):
#             formatted += f"Opportunité {i} :\n"
#             formatted += f"Titre : {item.get('title', 'Sans titre')}\n"
#             formatted += f"Source : {item.get('source', 'Non précisé')}\n"
#             formatted += f"URL : {item.get('url', 'Non précisé')}\n"
#             formatted += f"Extrait : {item.get('snippet', 'Non précisé')[:300]}...\n\n"
#         return formatted

#     def _call_claude(self, input_text: str) -> Dict:
#         """Appelle Claude avec Tool Calling"""
#         try:
#             response = self.client.messages.create(
#                 model=self.model,
#                 max_tokens=4096,
#                 temperature=float(os.getenv("CLAUDE_TEMPERATURE", 0.1)),
#                 system=self.system_prompt,
#                 tools=[{
#                     "name": "classifier",
#                     "description": "Classifie et analyse les opportunités commerciales",
#                     "input_schema": {
#                         "type": "object",
#                         "properties": {
#                             "opportunities": {
#                                 "type": "array",
#                                 "items": {
#                                     "type": "object",
#                                     "properties": {
#                                         "title": {"type": "string"},
#                                         "source": {"type": "string"},
#                                         "url": {"type": "string"},
#                                         "budget": {"type": "string"},
#                                         "deadline": {"type": "string"},
#                                         "organizer": {"type": "string"},
#                                         "domain": {
#                                             "type": "string",
#                                             "enum": ["ia", "devops", "data", "developpement", "bureautique", "autre"]
#                                         },
#                                         "summary": {"type": "string"},
#                                         "score": {"type": "integer", "minimum": 0, "maximum": 100},
#                                         "confidence": {"type": "number", "minimum": 0, "maximum": 1},
#                                         "reason": {"type": "string"}
#                                     },
#                                     "required": ["title", "source", "domain", "summary", "score", "confidence"]
#                                 }
#                             },
#                             "total": {"type": "integer"}
#                         },
#                         "required": ["opportunities", "total"]
#                     }
#                 }],
#                 messages=[{"role": "user", "content": input_text}]
#             )

#             # Extraire le JSON de la réponse
#             content = response.content[0].text
#             return self._extract_json(content)

#         except Exception as e:
#             logger.error(f"❌ Erreur Claude: {e}")
#             return {"opportunities": [], "total": 0}

#     def _extract_json(self, text: str) -> Dict:
#         """Extrait le JSON de la réponse de Claude"""
#         import re
#         try:
#             match = re.search(r'```json\s*(\{.*?\})\s*```', text, re.DOTALL)
#             if match:
#                 return json.loads(match.group(1))
#             match = re.search(r'(\{.*\})', text, re.DOTALL)
#             if match:
#                 return json.loads(match.group(1))
#             return {"opportunities": [], "total": 0}
#         except json.JSONDecodeError:
#             logger.error("❌ Erreur parsing JSON")
#             return {"opportunities": [], "total": 0}

#     def _parse_response(self, response: Dict) -> Dict:
#         """Parse la réponse de Claude"""
#         return response



# # ============================================================
# # ORCHESTRATEUR M1 — VEILLE MARCHÉ (AVEC GEMINI)
# # ============================================================

# import os
# import json
# import yaml
# import logging
# from typing import Dict, List, Any
# import google.generativeai as genai
# from dotenv import load_dotenv

# from app.services.search.search_manager import SearchManager
# from app.services.validation.validator import Validator

# load_dotenv()
# logger = logging.getLogger(__name__)

# class VeilleOrchestrator:
#     """Orchestrateur pour le module M1 avec Google Gemini"""

#     def __init__(self):
#         # --- Configuration de Gemini ---
#         genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))
#         self.model = genai.GenerativeModel('gemini-2.5-flash')  # na 'gemini-1.5-flash'
        
#         self.search_manager = SearchManager()
#         self.validator = Validator()

#         # Charger les prompts
#         self.system_prompt = self._load_prompt("app/prompts/m1/veille.yaml")

#     def _load_prompt(self, path: str) -> str:
#         """Charge le prompt depuis un fichier YAML"""
#         try:
#             with open(path, 'r', encoding='utf-8') as f:
#                 config = yaml.safe_load(f)

#             prompt = (
#                 config.get("role", "") + "\n\n" +
#                 config.get("task", "") + "\n\n" +
#                 config.get("format", "") + "\n\n" +
#                 config.get("context", "") + "\n\n" +
#                 "EXEMPLES :\n" + config.get("examples", "") + "\n\n" +
#                 config.get("security", "")
#             )
#             logger.info(f"✅ Prompt chargé: {path}")
#             return prompt
#         except Exception as e:
#             logger.error(f"❌ Erreur chargement prompt {path}: {e}")
#             return ""

#     def analyser_opportunites(self, query: str) -> Dict[str, Any]:
#         """
#         Analyse les opportunités pour une requête donnée avec Gemini

#         Args:
#             query (str): La requête de recherche

#         Returns:
#             Dict: Résultats structurés
#         """
#         try:
#             # 1. Rechercher les opportunités
#             results = self.search_manager.search_and_merge(query)

#             if not results:
#                 return {
#                     "success": True,
#                     "data": {
#                         "opportunities": [],
#                         "total": 0,
#                         "message": "Aucun résultat trouvé"
#                     }
#                 }

#             # 2. Préparer les données pour Gemini
#             input_text = self._format_results_for_claude(results)

#             # 3. Appeler Gemini
#             response = self._call_gemini(input_text)

#             # 4. Parser la réponse
#             parsed = self._parse_response(response)

#             # 5. Valider les données
#             validated = self.validator.validate_batch(parsed.get("opportunities", []))

#             return {
#                 "success": True,
#                 "data": {
#                     "opportunities": validated,
#                     "total": len(validated),
#                     "validated_count": len([o for o in validated if o.get("status") == "validated"])
#                 }
#             }

#         except Exception as e:
#             logger.error(f"❌ Erreur: {e}")
#             return {
#                 "success": False,
#                 "data": {},
#                 "error": str(e)
#             }

#     def _format_results_for_claude(self, results: List[Dict]) -> str:
#         """Formate les résultats pour Gemini"""
#         formatted = "Voici une liste d'opportunités à analyser :\n\n"
#         for i, item in enumerate(results, 1):
#             formatted += f"Opportunité {i} :\n"
#             formatted += f"Titre : {item.get('title', 'Sans titre')}\n"
#             formatted += f"Source : {item.get('source', 'Non précisé')}\n"
#             formatted += f"URL : {item.get('url', 'Non précisé')}\n"
#             formatted += f"Extrait : {item.get('snippet', 'Non précisé')[:300]}...\n\n"
#         return formatted

#     def _call_gemini(self, input_text: str) -> str:
#         """Appelle Google Gemini avec Tool Calling"""
#         try:
#             # Construire le prompt complet
#             full_prompt = self.system_prompt + "\n\n" + input_text + "\n\n" + """
#             IMPORTANT : Tu dois répondre UNIQUEMENT au format JSON suivant :

#             {
#               "opportunities": [
#                 {
#                   "title": "...",
#                   "source": "...",
#                   "url": "...",
#                   "budget": "...",
#                   "deadline": "...",
#                   "organizer": "...",
#                   "domain": "ia|devops|data|developpement|bureautique|autre",
#                   "summary": "...",
#                   "score": 85,
#                   "confidence": 0.92,
#                   "reason": "..."
#                 }
#               ],
#               "total": 20
#             }

#             Ne mets PAS d'autres commentaires. Réponds UNIQUEMENT le JSON.
#             """

#             # Appeler Gemini
#             response = self.model.generate_content(
#                 full_prompt,
#                 generation_config={
#                     "temperature": 0.1,
#                     "max_output_tokens": 4096,
#                 }
#             )

#             # Extraire le texte de la réponse
#             text_response = response.text
#             logger.info(f"✅ Réponse Gemini reçue ({len(text_response)} caractères)")

#             return self._extract_json(text_response)

#         except Exception as e:
#             logger.error(f"❌ Erreur Gemini: {e}")
#             return {"opportunities": [], "total": 0}

#     def _extract_json(self, text: str) -> Dict:
#         """Extrait le JSON de la réponse de Gemini"""
#         import re
#         try:
#             # Essayer de trouver un bloc JSON
#             match = re.search(r'```json\s*(\{.*?\})\s*```', text, re.DOTALL)
#             if match:
#                 return json.loads(match.group(1))
            
#             # Essayer de trouver des accolades simples
#             match = re.search(r'(\{.*\})', text, re.DOTALL)
#             if match:
#                 return json.loads(match.group(1))
            
#             # Si rien ne marche, retourner vide
#             logger.warning("⚠️ Aucun JSON trouvé dans la réponse")
#             return {"opportunities": [], "total": 0}
            
#         except json.JSONDecodeError as e:
#             logger.error(f"❌ Erreur parsing JSON: {e}")
#             return {"opportunities": [], "total": 0}

#     def _parse_response(self, response: Dict) -> Dict:
#         """Parse la réponse de Gemini"""
#         return response