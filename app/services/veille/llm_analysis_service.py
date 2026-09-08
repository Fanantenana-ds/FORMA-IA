# app/services/veille/llm_analysis_service.py
# ============================================================
# SERVICE ANALYSE LLM — Groq uniquement
# ============================================================
# Responsabilité unique : construire le prompt à partir de
# veille.yaml + des sources, appeler Groq, retourner le JSON
# brut. Ne fait NI classification finale, NI scoring final —
# ces décisions restent en Python déterministe (services dédiés),
# conformément à l'architecture validée : le LLM comprend,
# Python décide.
#
# CORRECTIF V1.1 :
# L'API Groq exige que le mot "json" apparaisse littéralement
# dans les messages envoyés quand response_format={"type":
# "json_object"} est utilisé (erreur 400 sinon). _ensure_json_keyword
# garantit cette contrainte indépendamment du contenu de
# veille.yaml, pour ne jamais dépendre d'une future édition du
# prompt métier.
# ============================================================

import json
import logging
import os
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx
from openai import AsyncOpenAI

from app.utils.retry import retry_with_backoff
from app.utils.url_utils import normalize_url

logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parents[3]
PROMPTS_DIR = BASE_DIR / "app" / "prompts" / "m1"
VEILLE_YAML_PATH = PROMPTS_DIR / "veille.yaml"

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GROQ_MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-20b")
GROQ_TIMEOUT = float(os.getenv("GROQ_TIMEOUT", "20"))
# 1200 était trop juste pour openai/gpt-oss-120b avec reasoning
# activé, même en "low" : le JSON de sortie (jusqu'à 4 sources,
# champs reason/summary/flags) peut dépasser ce budget.
GROQ_MAX_OUTPUT_TOKENS = int(os.getenv("GROQ_MAX_OUTPUT_TOKENS", "2500"))

MAX_PROMPT_CHARS = int(os.getenv("MAX_PROMPT_CHARS", "18000"))
MAX_SOURCE_CHARS_TOTAL = int(os.getenv("MAX_SOURCE_CHARS_TOTAL", "4500"))
MAX_SOURCE_CHARS_EACH = int(os.getenv("MAX_SOURCE_CHARS_EACH", "1000"))

RETRY_MAX_ATTEMPTS = int(os.getenv("RETRY_MAX_ATTEMPTS", "3"))
RETRY_BASE_DELAY = float(os.getenv("RETRY_BASE_DELAY", "1.0"))

# Ce texte est ajouté UNIQUEMENT si le mot "json" est absent du
# prompt final (donc en principe jamais si veille.yaml est à jour,
# mais c'est le filet de sécurité qui évite l'erreur 400 de Groq).
JSON_SAFETY_SUFFIX = (
    "\n\n===== FORMAT DE SORTIE =====\n"
    "Réponds UNIQUEMENT avec un objet JSON valide, "
    "sans texte avant ni après, sans bloc markdown."
)


class LLMAnalysisService:
    """Analyse factuelle des sources via Groq, pilotée par veille.yaml."""

    def __init__(self):
        self.model = GROQ_MODEL
        self.client: Optional[AsyncOpenAI] = None

        if GROQ_API_KEY:
            self.client = AsyncOpenAI(
                api_key=GROQ_API_KEY,
                base_url="https://api.groq.com/openai/v1",
                timeout=GROQ_TIMEOUT,
            )
            logger.info("🤖 GROQ configuré : %s", self.model)
        else:
            logger.warning("⚠️ GROQ_API_KEY absente")

        self.veille_yaml_text = self._load_raw_yaml(VEILLE_YAML_PATH)
        logger.info("✅ Prompt veille.yaml chargé")

        if "json" not in self.veille_yaml_text.lower():
            logger.warning(
                "⚠️ veille.yaml ne contient pas le mot 'json' — "
                "le filet de sécurité _ensure_json_keyword() sera "
                "systématiquement activé. Envisage de corriger le "
                "YAML directement pour un prompt plus propre."
            )

    # --------------------------------------------------------
    # CHARGEMENT YAML
    # --------------------------------------------------------

    @staticmethod
    def _load_raw_yaml(path: Path) -> str:
        if not path.exists():
            raise FileNotFoundError(f"Prompt introuvable : {path}")

        try:
            with open(path, "r", encoding="utf-8") as file:
                content = file.read()
        except OSError as exc:
            raise RuntimeError(f"Impossible de lire {path}") from exc

        if not content.strip():
            raise ValueError(f"Prompt vide : {path}")

        return content

    # --------------------------------------------------------
    # CONSTRUCTION DU PROMPT
    # --------------------------------------------------------

    @staticmethod
    def _replace_placeholders(
        template: str, query: str, current_date: str, results_text: str
    ) -> str:
        replacements = {
            "{{QUERY}}": query,
            "{{REQUETE}}": query,
            "{{REQUÊTE}}": query,
            "{{DATE_DU_JOUR}}": current_date,
            "{{DATE}}": current_date,
            "{{RESULTATS_BRUTS}}": results_text,
            "{{RÉSULTATS_BRUTS}}": results_text,
            "{{RESULTATS}}": results_text,
            "{{RÉSULTATS}}": results_text,
        }

        rendered = template
        for placeholder, value in replacements.items():
            rendered = rendered.replace(placeholder, value)

        return rendered

    def _build_source_blocks(self, results: List[Dict[str, Any]]) -> str:
        blocks = []
        total_chars = 0

        for index, result in enumerate(results, start=1):
            if not isinstance(result, dict):
                continue

            title = str(result.get("title", "")).strip()
            url = normalize_url(result.get("url", ""))
            content = str(
                result.get("content", "") or result.get("snippet", "")
            ).strip()[:MAX_SOURCE_CHARS_EACH]

            block = (
                f"===== RESULTAT {index} =====\n"
                f"TITRE: {title}\n"
                f"URL: {url}\n"
                f"CONTENU:\n{content}\n"
            )

            projected = total_chars + len(block)
            if projected > MAX_SOURCE_CHARS_TOTAL:
                break

            blocks.append(block)
            total_chars = projected

        return "\n".join(blocks)

    def _build_prompt(self, query: str, results: List[Dict[str, Any]]) -> str:
        current_date = datetime.now().strftime("%Y-%m-%d")
        results_text = self._build_source_blocks(results)

        prompt = self._replace_placeholders(
            self.veille_yaml_text, query, current_date, results_text
        )

        yaml_lower = self.veille_yaml_text
        has_query = any(
            p in yaml_lower for p in ["{{QUERY}}", "{{REQUETE}}", "{{REQUÊTE}}"]
        )
        has_date = any(p in yaml_lower for p in ["{{DATE_DU_JOUR}}", "{{DATE}}"])
        has_results = any(
            p in yaml_lower
            for p in [
                "{{RESULTATS_BRUTS}}", "{{RÉSULTATS_BRUTS}}",
                "{{RESULTATS}}", "{{RÉSULTATS}}",
            ]
        )

        additions = []
        if not has_query:
            additions.append(f"\n\n===== REQUÊTE UTILISATEUR =====\n{query}\n")
        if not has_date:
            additions.append(f"\n\n===== DATE ACTUELLE =====\n{current_date}\n")
        if not has_results:
            additions.append(f"\n\n===== RÉSULTATS TAVILY =====\n{results_text}\n")

        if additions:
            prompt += "".join(additions)

        return prompt

    @staticmethod
    def _ensure_json_keyword(prompt: str) -> str:
        """
        Garantit que le mot 'json' apparaît dans le prompt final —
        exigence technique STRICTE de l'API Groq quand
        response_format={"type": "json_object"} est utilisé.

        Sans ce garde-fou : erreur 400 systématique, quel que soit
        le contenu de veille.yaml (c'est exactement ce qui s'est
        produit : "'messages' must contain the word 'json'...").
        """
        if "json" not in prompt.lower():
            prompt += JSON_SAFETY_SUFFIX
        return prompt

    def build_prompt_with_budget(
        self, query: str, results: List[Dict[str, Any]]
    ) -> str:
        """Conserve le YAML complet, réduit uniquement les sources si besoin."""

        prompt = self._build_prompt(query, results)

        if len(prompt) <= MAX_PROMPT_CHARS:
            return self._ensure_json_keyword(prompt)

        logger.warning(
            "⚠️ Prompt trop grand : %d caractères. Réduction des sources.",
            len(prompt),
        )

        reduced_results = list(results)
        while len(prompt) > MAX_PROMPT_CHARS and len(reduced_results) > 1:
            reduced_results.pop()
            prompt = self._build_prompt(query, reduced_results)

        if len(prompt) > MAX_PROMPT_CHARS:
            logger.warning("⚠️ Le YAML seul est proche de la limite de prompt.")

        logger.info(
            "📦 Prompt final : %d caractères / %d résultats",
            len(prompt),
            len(reduced_results),
        )

        return self._ensure_json_keyword(prompt)

    # --------------------------------------------------------
    # APPEL GROQ (avec retry/backoff)
    # --------------------------------------------------------

    async def _do_call(self, prompt: str):
        """Un seul essai — rejouable par retry_with_backoff."""
        return await self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,
            max_tokens=GROQ_MAX_OUTPUT_TOKENS,
            response_format={"type": "json_object"},
            # IMPORTANT : openai/gpt-oss-120b est un modèle de
            # raisonnement sur Groq. Par défaut (reasoning_effort=
            # "medium"), le raisonnement interne peut épuiser tout
            # le budget max_tokens AVANT que le JSON final ne soit
            # généré -> erreur "json_validate_failed / max completion
            # tokens reached before generating a valid document".
            # "low" laisse plus de marge pour la réponse elle-même.
            reasoning_effort="low",
        )

    async def analyze(
        self, query: str, results: List[Dict[str, Any]]
    ) -> Optional[Dict[str, Any]]:
        """
        Construit le prompt et interroge Groq. Retourne le JSON
        brut du modèle, ou None en cas d'échec (réseau ou format).
        """

        if self.client is None:
            logger.warning("⚠️ GROQ indisponible")
            return None

        prompt = self.build_prompt_with_budget(query, results)

        logger.info("📤 Envoi à GROQ : %d sources", len(results))
        for i, r in enumerate(results, start=1):
            content_preview = str(
                r.get("content", "") or r.get("snippet", "")
            )[:150]
            logger.info(
                "   [%d] %s | contenu: %s...",
                i, str(r.get("title", "?"))[:60], content_preview,
            )
        logger.info("📦 Taille prompt : %d caractères", len(prompt))

        start = time.perf_counter()

        try:
            response = await retry_with_backoff(
                self._do_call,
                prompt,
                max_retries=RETRY_MAX_ATTEMPTS,
                base_delay=RETRY_BASE_DELAY,
                retryable_exceptions=(httpx.TimeoutException, httpx.HTTPError),
                label="Groq",
            )

            elapsed = time.perf_counter() - start
            logger.info("⏱️ Groq : %.3fs", elapsed)

            if not response.choices:
                logger.error("❌ GROQ : aucune choice")
                return None

            content = response.choices[0].message.content
            if not content:
                logger.error("❌ GROQ : réponse vide")
                return None

            # Erreur de parsing JSON : PAS transitoire, pas de retry.
            try:
                data = json.loads(content)
            except json.JSONDecodeError as exc:
                logger.error("❌ GROQ : JSON invalide : %s", exc)
                logger.error("Réponse brute : %s", content[:2500])
                return None

            if not isinstance(data, dict):
                return None

            if "opportunities" not in data:
                logger.error("❌ GROQ : opportunities absente")
                return None

            if not isinstance(data["opportunities"], list):
                logger.error("❌ GROQ : opportunities invalide")
                return None

            logger.info(
                "✅ GROQ : réponse JSON valide — %d opportunités",
                len(data["opportunities"]),
            )

            return data

        # BadRequestError (400) inclut l'erreur "must contain the word json"
        # -> PAS transitoire, ne doit jamais être retryée.
        except httpx.HTTPStatusError as exc:
            logger.error(
                "❌ GROQ [%s] : erreur HTTP non transitoire (%s) — pas de retry",
                self.model,
                exc,
            )
            return None

        except (httpx.TimeoutException, httpx.HTTPError) as exc:
            logger.exception("❌ GROQ [%s] (après retries) : %s", self.model, exc)
            return None

        except Exception as exc:
            logger.exception("❌ GROQ [%s] : %s", self.model, exc)
            return None