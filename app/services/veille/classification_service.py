# # app/services/veille/classification_service.py
# # ============================================================
# # SERVICE CLASSIFICATION — décision déterministe Python
# # ============================================================
# # Le domaine (ia / devops / data / developpement / bureautique /
# # autre) est décidé par dictionnaire de mots-clés en Python,
# # PAS par le LLM. Choix architectural volontaire : garantit un
# # résultat reproductible et mesurable pour le benchmark de
# # précision >85% exigé par le CDC (§4).
# #
# # classification.yaml reste chargé comme référence documentaire
# # (traçabilité, cohérence avec la norme RTFCE) même si la
# # décision finale est ici, en Python.
# # ============================================================

# import logging
# import os
# from pathlib import Path
# from typing import Any, Dict

# import yaml

# logger = logging.getLogger(__name__)

# BASE_DIR = Path(__file__).resolve().parents[3]
# CLASSIFICATION_YAML_PATH = (
#     BASE_DIR / "app" / "prompts" / "m1" / "classification.yaml"
# )

# DOMAIN_KEYWORDS = {
#     "ia": [
#         "ia", "intelligence artificielle", "artificial intelligence", "ai",
#         "machine learning", "ml", "deep learning", "llm", "claude",
#         "chatgpt", "gpt", "gemini", "mistral", "prompt",
#         "prompt engineering", "agent ia", "agent", "rag", "nlp",
#         "fine-tuning", "embedding", "formation ia", "conseil ia",
#         "intégration ia",
#     ],
#     "data": [
#         "data", "données", "big data", "analytics", "sql",
#         "base de données", "data warehouse", "etl", "bi",
#         "business intelligence", "dashboard", "tableau de bord",
#         "visualisation", "power bi", "tableau", "looker",
#         "statistiques", "analyse prédictive", "data scientist",
#         "data analyst", "data engineer",
#     ],
#     "devops": [
#         "devops", "cloud", "aws", "azure", "gcp", "oci", "kubernetes",
#         "k8s", "docker", "conteneurisation", "ci/cd", "pipeline",
#         "intégration continue", "déploiement continu", "infrastructure",
#         "migration cloud", "scaling", "sre", "monitoring", "observabilité",
#     ],
#     "developpement": [
#         "développement", "developpement", "development", "programmation",
#         "code", "application", "web", "mobile", "desktop", "api", "rest",
#         "microservices", "backend", "frontend", "fullstack", "react",
#         "angular", "vue", "node", "django", "fastapi", "logiciel", "erp",
#         "crm", "développeur", "developpeur", "developer", "ingénieur logiciel",
#     ],
#     "bureautique": [
#         "excel", "word", "powerpoint", "outlook", "office", "bureautique",
#         "google workspace", "suite office", "formation excel",
#         "assistance administrative",
#     ],
# }


# def _load_yaml_reference(path: Path) -> Dict[str, Any]:
#     if not path.exists():
#         logger.warning("⚠️ Prompt de référence absent : %s", path)
#         return {}

#     try:
#         with open(path, "r", encoding="utf-8") as file:
#             data = yaml.safe_load(file)
#     except yaml.YAMLError as exc:
#         logger.error("❌ YAML invalide : %s", path)
#         raise ValueError(f"YAML invalide : {path}") from exc

#     return data if isinstance(data, dict) else {}


# class ClassificationService:
#     """Classification par domaine et détection géographique."""

#     def __init__(self):
#         self.classification_reference = _load_yaml_reference(
#             CLASSIFICATION_YAML_PATH
#         )
#         logger.info("✅ classification.yaml chargé (référence)")

#     def classify(self, opportunity: Dict[str, Any]) -> Dict[str, Any]:
#         title = str(opportunity.get("title", "")).lower()
#         summary = str(opportunity.get("summary", "") or "").lower()
#         text = f"{title} {summary}"

#         best_domain = "autre"
#         best_score = 0
#         matches = []

#         for domain, keywords in DOMAIN_KEYWORDS.items():
#             current_score = 0
#             found = []

#             for keyword in keywords:
#                 if keyword in text:
#                     current_score += 1
#                     found.append(keyword)

#             if current_score > best_score:
#                 best_score = current_score
#                 best_domain = domain
#                 matches = found

#         confidence = min(0.95, 0.50 + (best_score * 0.05))

#         return {
#             "domain": best_domain,
#             "confidence": round(confidence, 3),
#             "matched_keywords": matches[:5],
#             "classification_reason": "Classification technique basée sur les mots-clés.",
#         }

#     @staticmethod
#     def detect_country(opportunity: Dict[str, Any]) -> str:
#         text = (
#             f"{opportunity.get('title', '')} "
#             f"{opportunity.get('summary', '') or ''} "
#             f"{opportunity.get('location', '') or ''}"
#         ).lower()
#         url = str(opportunity.get("url", "")).lower()

#         if "madagascar" in text or "antananarivo" in text or ".mg" in url:
#             return "Madagascar"

#         return "International"





# app/services/veille/classification_service.py
# ============================================================
# SERVICE CLASSIFICATION — décision déterministe Python
# ============================================================
# Le domaine (ia / devops / data / developpement / bureautique /
# autre) est décidé par dictionnaire de mots-clés en Python,
# PAS par le LLM. Choix architectural volontaire : garantit un
# résultat reproductible et mesurable pour le benchmark de
# précision >85% exigé par le CDC (§4).
#
# classification.yaml reste chargé comme référence documentaire
# (traçabilité, cohérence avec la norme RTFCE) même si la
# décision finale est ici, en Python.
# ============================================================

import logging
import os
from pathlib import Path
from typing import Any, Dict

import yaml

logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parents[3]
CLASSIFICATION_YAML_PATH = (
    BASE_DIR / "app" / "prompts" / "m1" / "classification.yaml"
)

DOMAIN_KEYWORDS = {
    "ia": [
        "ia", "intelligence artificielle", "artificial intelligence", "ai",
        "machine learning", "ml", "deep learning", "llm", "claude",
        "chatgpt", "gpt", "gemini", "mistral", "prompt",
        "prompt engineering", "agent ia", "agent", "rag", "nlp",
        "fine-tuning", "embedding", "formation ia", "conseil ia",
        "intégration ia",
    ],
    "data": [
        "data", "données", "big data", "analytics", "sql",
        "base de données", "data warehouse", "etl", "bi",
        "business intelligence", "dashboard", "tableau de bord",
        "visualisation", "power bi", "tableau", "looker",
        "statistiques", "analyse prédictive", "data scientist",
        "data analyst", "data engineer",
    ],
    "devops": [
        "devops", "cloud", "aws", "azure", "gcp", "oci", "kubernetes",
        "k8s", "docker", "conteneurisation", "ci/cd", "pipeline",
        "intégration continue", "déploiement continu", "infrastructure",
        "migration cloud", "scaling", "sre", "monitoring", "observabilité",
    ],
    "developpement": [
        "développement", "developpement", "development", "programmation",
        "code", "application", "web", "mobile", "desktop", "api", "rest",
        "microservices", "backend", "frontend", "fullstack", "react",
        "angular", "vue", "node", "django", "fastapi", "logiciel", "erp",
        "crm", "développeur", "developpeur", "developer", "ingénieur logiciel",
    ],
    "bureautique": [
        "excel", "word", "powerpoint", "outlook", "office", "bureautique",
        "google workspace", "suite office", "formation excel",
        "assistance administrative",
    ],
}


def _load_yaml_reference(path: Path) -> Dict[str, Any]:
    if not path.exists():
        logger.warning("⚠️ Prompt de référence absent : %s", path)
        return {}

    try:
        with open(path, "r", encoding="utf-8") as file:
            data = yaml.safe_load(file)
    except yaml.YAMLError as exc:
        logger.error("❌ YAML invalide : %s", path)
        raise ValueError(f"YAML invalide : {path}") from exc

    return data if isinstance(data, dict) else {}


class ClassificationService:
    """Classification par domaine et détection géographique."""

    def __init__(self):
        self.classification_reference = _load_yaml_reference(
            CLASSIFICATION_YAML_PATH
        )
        logger.info("✅ classification.yaml chargé (référence)")

    def classify(self, opportunity: Dict[str, Any]) -> Dict[str, Any]:
        title = str(opportunity.get("title", "")).lower()
        summary = str(opportunity.get("summary", "") or "").lower()
        text = f"{title} {summary}"

        best_domain = "autre"
        best_score = 0
        matches = []

        for domain, keywords in DOMAIN_KEYWORDS.items():
            current_score = 0
            found = []

            for keyword in keywords:
                if keyword in text:
                    current_score += 1
                    found.append(keyword)

            if current_score > best_score:
                best_score = current_score
                best_domain = domain
                matches = found

        confidence = min(0.95, 0.50 + (best_score * 0.05))

        return {
            "domain": best_domain,
            "confidence": round(confidence, 3),
            "matched_keywords": matches[:5],
            "classification_reason": "Classification technique basée sur les mots-clés.",
        }

    @staticmethod
    def detect_country(opportunity: Dict[str, Any]) -> str:
        text = (
            f"{opportunity.get('title', '')} "
            f"{opportunity.get('summary', '') or ''} "
            f"{opportunity.get('location', '') or ''} "
            f"{opportunity.get('organizer', '') or ''}"
        ).lower()
        url = str(opportunity.get("url", "")).lower()

        # Patterns d'URL Madagascar : à la fois "exemple.mg" (TLD)
        # ET "mg.exemple.com" (sous-domaine, ex: mg.linkedin.com,
        # très fréquent pour les offres LinkedIn Madagascar — raté
        # par un simple ".mg" in url qui ne matche que le TLD).
        url_indicates_mg = (
            ".mg" in url
            or "//mg." in url
            or ".mg." in url
            or "://mg" in url
        )

        if "madagascar" in text or "antananarivo" in text or url_indicates_mg:
            return "Madagascar"

        return "International"