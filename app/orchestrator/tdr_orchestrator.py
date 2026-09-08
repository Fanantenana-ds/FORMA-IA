# # app/orchestrator/tdr_orchestrator.py
# # ============================================================
# # FORMA-IA — M2 GÉNÉRATION DE TDR — ORCHESTRATEUR
# # ============================================================
# # Version : V1.0 — Architecture modulaire
# #
# # Ce fichier coordonne :
# #   - Chargement du prompt RTFCE (tdr.yaml)
# #   - Appel à l'API Groq (via llm_analysis_service)
# #   - Validation du JSON de sortie
# #   - Retour du TDR structuré
# # ============================================================

# import logging
# import json
# import os
# import time
# import re
# from typing import Dict, Any, List, Optional

# from app.services.veille.llm_analysis_service import LLMAnalysisService
# from app.utils.prompts_loader import load_prompt

# logger = logging.getLogger(__name__)

# class TdrOrchestrator:
#     """
#     Orchestrateur pour la génération de TDR (M2)
#     Utilise le même service LLM que M1 (Groq)
#     """
    
#     def __init__(self):
#         logger.info("🚀 M2: Initialisation TDR Orchestrator")
#         self.llm_service = LLMAnalysisService()
#         self.prompt_template = self._load_prompt()
#         self.max_tokens = int(os.getenv("TDR_MAX_TOKENS", "3000"))
#         self.temperature = float(os.getenv("TDR_TEMPERATURE", "0.3"))
#         logger.info("✅ M2: TDR Orchestrator prêt")
    
#     def _load_prompt(self) -> str:
#         """Charge le prompt tdr.yaml"""
#         try:
#             prompt = load_prompt("m2/tdr.yaml")
#             logger.info("✅ Prompt tdr.yaml chargé")
#             return prompt
#         except Exception as e:
#             logger.error(f"❌ Erreur chargement prompt: {e}")
#             # Fallback : prompt simple
#             return """
#             Rédige un TDR pour la formation suivante :
#             {BRIEF}
            
#             Retourne un JSON structuré avec : titre, contexte, objectifs_generaux,
#             objectifs_specifiques, public_cible, programme, methodologie,
#             evaluation, budget, calendrier, contact.
#             """
    
#     async def generate(self, brief: Dict[str, Any]) -> Dict[str, Any]:
#         """
#         Génère un TDR à partir d'un brief structuré
        
#         Args:
#             brief: Dict avec client, objectifs, public, duree, etc.
            
#         Returns:
#             TDR structuré en JSON
#         """
#         start_time = time.perf_counter()
#         logger.info("=" * 60)
#         logger.info("🚀 M2 TDR — DÉBUT")
#         logger.info(f"📝 Client : {brief.get('client', 'Non précisé')}")
#         logger.info(f"📝 Public : {brief.get('public', 'Non précisé')}")
#         logger.info(f"📝 Durée : {brief.get('duree', 'Non précisée')}")
#         logger.info("=" * 60)
        
#         try:
#             # 1. Valider le brief
#             if not self._validate_brief(brief):
#                 return {"error": "Brief invalide (client, objectifs, public, duree requis)", "status": "error"}
            
#             # 2. Construire le prompt
#             prompt = self._build_prompt(brief)

#             logger.info(f"📦 Taille du prompt: {len(prompt)} caractères")
            
#             # 3. Appeler l'API Groq
#             response = await self._call_api(prompt)
            
#             if not response:
#                 return {"error": "Erreur API Groq", "status": "error"}
            
#             # 4. Extraire le JSON de la réponse
#             tdr_content = self._extract_json(response)
#             if not tdr_content:
#                 logger.warning(f"⚠️ Réponse brute: {response[:300]}...")
#                 return {"error": "Format JSON invalide", "status": "error"}
            
#             # 5. Valider le contenu
#             if not self._validate_tdr(tdr_content):
#                 return {"error": "TDR invalide (champs manquants)", "status": "error"}
            
#             # 6. Ajouter les métadonnées
#             elapsed = time.perf_counter() - start_time
#             tdr_content["generated_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
#             tdr_content["generation_time_seconds"] = round(elapsed, 2)
#             tdr_content["status"] = "draft"
            
#             logger.info(f"🏁 M2 TDR — FIN")
#             logger.info(f"✅ TDR généré en {elapsed:.2f}s")
#             logger.info(f"📄 Titre : {tdr_content.get('titre', 'Non défini')}")
#             logger.info("=" * 60)
            
#             return tdr_content
            
#         except Exception as e:
#             logger.error(f"❌ Erreur génération TDR: {e}")
#             return {"error": str(e), "status": "error"}
    
#     async def _call_api(self, prompt: str) -> Optional[str]:
#         """Appelle l'API Groq en réutilisant le service de M1"""
#         try:
#             # Réutiliser la méthode analyze de llm_analysis_service
#             # On crée une source factice pour utiliser la méthode existante
#             dummy_result = {
#                 "content": prompt,
#                 "title": "TDR Generation"
#             }
#             result = await self.llm_service.analyze("Génération de TDR", [dummy_result])
            
#             if result and "opportunities" in result:
#                 # La réponse est déjà un JSON structuré
#                 return json.dumps(result["opportunities"][0] if result["opportunities"] else {})
            
#             return None
            
#         except Exception as e:
#             logger.error(f"❌ Erreur appel API: {e}")
#             return None
    
#     def _validate_brief(self, brief: Dict[str, Any]) -> bool:
#         """Valide que le brief contient les champs obligatoires"""
#         required = ["client", "objectifs", "public", "duree"]
#         for field in required:
#             if field not in brief or not brief[field]:
#                 logger.error(f"❌ Champ manquant dans le brief: {field}")
#                 return False
#         return True
    
#     def _build_prompt(self, brief: Dict[str, Any]) -> str:
#         """Construit le prompt final en remplaçant {{BRIEF}}"""
#         brief_text = self._format_brief(brief)
#         return self.prompt_template.replace("{{BRIEF}}", brief_text)
    
#     def _format_brief(self, brief: Dict[str, Any]) -> str:
#         """Formate le brief en texte lisible pour le prompt"""
#         lines = []
#         lines.append(f"Client : {brief.get('client', 'Non précisé')}")
#         lines.append(f"Objectifs : {', '.join(brief.get('objectifs', []))}")
#         lines.append(f"Public cible : {brief.get('public', 'Non précisé')}")
#         lines.append(f"Durée : {brief.get('duree', 'Non précisée')}")
        
#         if brief.get('lieu'):
#             lines.append(f"Lieu : {brief['lieu']}")
#         if brief.get('budget'):
#             lines.append(f"Budget : {brief['budget']}")
#         if brief.get('deadline'):
#             lines.append(f"Échéance : {brief['deadline']}")
#         if brief.get('contenu'):
#             lines.append(f"Contenu spécifique : {brief['contenu']}")
#         if brief.get('contact'):
#             lines.append(f"Contact : {brief['contact']}")
        
#         return "\n".join(lines)
    
#     def _extract_json(self, response: str) -> Optional[Dict[str, Any]]:
#         """Extrait le JSON de la réponse de l'API"""
#         if not response:
#             return None
        
#         try:
#             # Essayer de parser directement
#             return json.loads(response)
#         except json.JSONDecodeError:
#             pass
        
#         # Essayer d'extraire le JSON des backticks
#         json_match = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', response)
#         if json_match:
#             try:
#                 return json.loads(json_match.group(1))
#             except:
#                 pass
        
#         # Essayer de trouver un objet JSON dans le texte
#         json_match = re.search(r'\{[\s\S]*\}', response)
#         if json_match:
#             try:
#                 return json.loads(json_match.group(0))
#             except:
#                 pass
        
#         logger.warning("⚠️ Impossible d'extraire le JSON de la réponse")
#         return None
    
#     def _validate_tdr(self, tdr: Dict[str, Any]) -> bool:
#         """Valide que le TDR contient les champs obligatoires"""
#         required = ["titre", "contexte", "objectifs_generaux", "public_cible", "programme"]
#         for field in required:
#             if field not in tdr or not tdr[field]:
#                 logger.warning(f"⚠️ Champ manquant dans le TDR: {field}")
#                 return False
#         return True





# ============================================================
# FORMA-IA — M2 GÉNÉRATION DE TDR — ORCHESTRATEUR
# ============================================================
# Version : V1.1 — Correction bugs 1, 2, 3 (mismatch schéma yaml)
#
# Ce fichier coordonne :
#   - Chargement du prompt RTFCE (tdr.yaml)
#   - Appel à l'API Groq (via llm_analysis_service)
#   - Validation du JSON de sortie
#   - Retour du TDR structuré (aplati, cohérent avec TDRResponse)
# ============================================================

import logging
import json
import os
import time
import re
from typing import Dict, Any, List, Optional

from app.services.veille.llm_analysis_service import LLMAnalysisService
from app.utils.prompts_loader import load_prompt

logger = logging.getLogger(__name__)


class TdrOrchestrator:
    """
    Orchestrateur pour la génération de TDR (M2)
    Utilise le même service LLM que M1 (Groq) — migration Claude prévue
    """

    def __init__(self):
        logger.info("🚀 M2: Initialisation TDR Orchestrator")
        self.llm_service = LLMAnalysisService()
        self.prompt_template = self._load_prompt()
        self.max_tokens = int(os.getenv("TDR_MAX_TOKENS", "3000"))
        self.temperature = float(os.getenv("TDR_TEMPERATURE", "0.3"))
        logger.info("✅ M2: TDR Orchestrator prêt")

    def _load_prompt(self) -> str:
        """Charge le prompt tdr.yaml"""
        try:
            prompt = load_prompt("m2/tdr.yaml")
            logger.info("✅ Prompt tdr.yaml chargé")
            return prompt
        except Exception as e:
            logger.error(f"❌ Erreur chargement prompt: {e}")
            # Fallback : prompt simple (non conforme RTFCE — à corriger via bug 3)
            return """
            Rédige un TDR pour la formation suivante :
            {BRIEF}

            Retourne un JSON structuré avec : titre, contexte, objectifs_generaux,
            objectifs_specifiques, public_cible, programme, methodologie,
            evaluation, budget, calendrier, contact.
            """

    async def generate(self, brief: Dict[str, Any]) -> Dict[str, Any]:
        """
        Génère un TDR à partir d'un brief structuré

        Args:
            brief: Dict avec client, objectifs, public, duree, etc.

        Returns:
            TDR structuré en JSON (à plat), ou {"error": ..., "status": "error"}
        """
        start_time = time.perf_counter()
        logger.info("=" * 60)
        logger.info("🚀 M2 TDR — DÉBUT")
        logger.info(f"📝 Client : {brief.get('client', 'Non précisé')}")
        logger.info(f"📝 Public : {brief.get('public', 'Non précisé')}")
        logger.info(f"📝 Durée : {brief.get('duree', 'Non précisée')}")
        logger.info("=" * 60)

        try:
            # 1. Valider le brief
            if not self._validate_brief(brief):
                return {"error": "Brief invalide (client, objectifs, public, duree requis)", "status": "error"}

            # 2. Construire le prompt
            prompt = self._build_prompt(brief)
            logger.info(f"📦 Taille du prompt: {len(prompt)} caractères")

            # 3. Appeler l'API Groq
            response = await self._call_api(prompt)
            if not response:
                return {"error": "Erreur API Groq", "status": "error"}

            # 4. Extraire le JSON de la réponse
            raw_content = self._extract_json(response)
            if not raw_content:
                logger.warning(f"⚠️ Réponse brute: {response[:300]}...")
                return {"error": "Format JSON invalide", "status": "error"}

            # 4bis. Aplatir la structure si elle suit le format du yaml
            #       ({"tdr": {"titre": ..., "sections": {...}}, "format": "markdown"})
            tdr_content = self._flatten_tdr(raw_content)

            # 5. Valider le contenu
            if not self._validate_tdr(tdr_content):
                return {"error": "TDR invalide (champs manquants)", "status": "error"}

            # 6. Ajouter les métadonnées
            elapsed = time.perf_counter() - start_time
            tdr_content["generated_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
            tdr_content["generation_time_seconds"] = round(elapsed, 2)
            tdr_content["status"] = "draft"

            logger.info(f"🏁 M2 TDR — FIN")
            logger.info(f"✅ TDR généré en {elapsed:.2f}s")
            logger.info(f"📄 Titre : {tdr_content.get('titre', 'Non défini')}")
            logger.info("=" * 60)

            return tdr_content

        except Exception as e:
            logger.error(f"❌ Erreur génération TDR: {e}")
            return {"error": str(e), "status": "error"}

    async def _call_api(self, prompt: str) -> Optional[str]:
        """Appelle l'API Groq en réutilisant le service de M1"""
        try:
            dummy_result = {
                "content": prompt,
                "title": "TDR Generation"
            }
            result = await self.llm_service.analyze("Génération de TDR", [dummy_result])

            if result and "opportunities" in result:
                return json.dumps(result["opportunities"][0] if result["opportunities"] else {})

            return None

        except Exception as e:
            logger.error(f"❌ Erreur appel API: {e}")
            return None

    def _validate_brief(self, brief: Dict[str, Any]) -> bool:
        """Valide que le brief contient les champs obligatoires"""
        required = ["client", "objectifs", "public", "duree"]
        for field in required:
            if field not in brief or not brief[field]:
                logger.error(f"❌ Champ manquant dans le brief: {field}")
                return False
        return True

    def _build_prompt(self, brief: Dict[str, Any]) -> str:
        """Construit le prompt final en remplaçant {{BRIEF}}"""
        brief_text = self._format_brief(brief)
        return self.prompt_template.replace("{{BRIEF}}", brief_text)

    def _format_brief(self, brief: Dict[str, Any]) -> str:
        """Formate le brief en texte lisible pour le prompt"""
        lines = []
        lines.append(f"Client : {brief.get('client', 'Non précisé')}")

        objectifs = brief.get('objectifs', '')
        if isinstance(objectifs, list):
            lines.append(f"Objectifs : {', '.join(objectifs)}")
        else:
            lines.append(f"Objectifs : {objectifs}")

        lines.append(f"Public cible : {brief.get('public', 'Non précisé')}")
        lines.append(f"Durée : {brief.get('duree', 'Non précisée')}")

        if brief.get('format'):
            lines.append(f"Format : {brief['format']}")
        if brief.get('lieu'):
            lines.append(f"Lieu : {brief['lieu']}")
        if brief.get('budget'):
            lines.append(f"Budget : {brief['budget']}")
        if brief.get('deadline'):
            lines.append(f"Échéance : {brief['deadline']}")
        if brief.get('contenu'):
            lines.append(f"Contenu spécifique : {brief['contenu']}")
        if brief.get('contact'):
            lines.append(f"Contact : {brief['contact']}")

        return "\n".join(lines)

    def _extract_json(self, response: str) -> Optional[Dict[str, Any]]:
        """Extrait le JSON de la réponse de l'API"""
        if not response:
            return None

        try:
            return json.loads(response)
        except json.JSONDecodeError:
            pass

        json_match = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', response)
        if json_match:
            try:
                return json.loads(json_match.group(1))
            except Exception:
                pass

        json_match = re.search(r'\{[\s\S]*\}', response)
        if json_match:
            try:
                return json.loads(json_match.group(0))
            except Exception:
                pass

        logger.warning("⚠️ Impossible d'extraire le JSON de la réponse")
        return None

    def _flatten_tdr(self, raw: Dict[str, Any]) -> Dict[str, Any]:
        """
        Aplati la structure imbriquée définie par prompts/m2/tdr.yaml :
            {"tdr": {"titre": ..., "sections": {"contexte": ..., "objectifs": ..., ...}}, "format": "markdown"}
        vers la structure à plat attendue par _validate_tdr / TDRResponse :
            {"titre": ..., "contexte": ..., "objectifs_generaux": ..., "public_cible": ..., "programme": ...}

        Si la réponse est déjà à plat (fallback prompt), la renvoie telle quelle.
        """
        if "tdr" in raw and isinstance(raw["tdr"], dict):
            tdr = raw["tdr"]
            sections = tdr.get("sections", {}) if isinstance(tdr.get("sections"), dict) else {}

            flat = {
                "titre": tdr.get("titre"),
                "contexte": sections.get("contexte"),
                "objectifs_generaux": sections.get("objectifs"),
                "public_cible": sections.get("public"),
                "programme": sections.get("contenu"),
                "methodologie": sections.get("methodologie"),
                "evaluation": sections.get("evaluation"),
                "budget": sections.get("budget"),
                "annexes": sections.get("annexes"),
                "format_source": raw.get("format", "markdown"),
            }
            return flat

        # Déjà à plat (fallback ou évolution future du prompt)
        return raw

    def _validate_tdr(self, tdr: Dict[str, Any]) -> bool:
        """Valide que le TDR contient les champs obligatoires"""
        required = ["titre", "contexte", "objectifs_generaux", "public_cible", "programme"]
        for field in required:
            if field not in tdr or not tdr[field]:
                logger.warning(f"⚠️ Champ manquant dans le TDR: {field}")
                return False
        return True