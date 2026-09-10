# app/services/tdr/tdr_service.py
# ============================================================
# SERVICE TDR — Appel Groq direct (sans LangChain)
# ============================================================
# Version : V2.0 — Fix KeyError sur .format() du prompt
# ============================================================

import json
import logging
import os
import re
import time
from pathlib import Path
from typing import Any, Dict, Optional

import httpx
import yaml
from openai import AsyncOpenAI

from app.utils.retry import retry_with_backoff

logger = logging.getLogger(__name__)

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GROQ_MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-20b")
GROQ_TIMEOUT = float(os.getenv("GROQ_TIMEOUT", "90"))
TDR_MAX_OUTPUT_TOKENS = int(os.getenv("TDR_MAX_OUTPUT_TOKENS", "4000"))
TDR_TEMPERATURE = float(os.getenv("TDR_TEMPERATURE", "0.3"))

# Chemin vers tdr.yaml
BASE_DIR = Path(__file__).resolve().parents[2]
TDR_YAML_PATH = BASE_DIR / "prompts" / "m2" / "tdr.yaml"


class TDRService:
    """Génération de TDR via Groq (API directe, sans LangChain)."""

    def __init__(self):
        if not GROQ_API_KEY:
            raise ValueError("GROQ_API_KEY manquante dans .env")

        self.client = AsyncOpenAI(
            api_key=GROQ_API_KEY,
            base_url="https://api.groq.com/openai/v1",
            timeout=GROQ_TIMEOUT,
        )
        self.model = GROQ_MODEL
        self.system_prompt = self._load_prompt()

    def _load_prompt(self) -> str:
        """Charge tdr.yaml et assemble le prompt."""
        if not TDR_YAML_PATH.exists():
            raise FileNotFoundError(f"Prompt introuvable : {TDR_YAML_PATH}")

        with open(TDR_YAML_PATH, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)

        parts = []
        for key in ["role", "task", "format", "context", "examples", "security"]:
            if key in data and data[key]:
                parts.append(str(data[key]).strip())

        prompt = "\n\n".join(parts)
        logger.info("✅ Prompt tdr.yaml chargé (%d chars)", len(prompt))
        return prompt

    def _build_prompt(self, brief: Dict[str, Any]) -> str:
        """
        Injecte le brief dans le prompt.
        
        ⚠️ Utilise replace() au lieu de format() car le prompt contient
        des JSON examples avec { et } qui provoqueraient un KeyError
        avec str.format().
        """
        prompt = self.system_prompt

        # ✅ Remplacements sécurisés (pas d'interprétation des { } du YAML)
        replacements = {
            "{client}": str(brief.get("client", "Non précisé")),
            "{objectifs}": str(brief.get("objectifs", "Non précisés")),
            "{public}": str(brief.get("public", "Non précisé")),
            "{duree}": str(brief.get("duree", "Non précisée")),
            "{format}": str(brief.get("format", "Présentiel")),
            "{budget}": str(brief.get("budget", "Non précisé")),
            "{lieu}": str(brief.get("lieu", "Non précisé")),
        }

        for placeholder, value in replacements.items():
            prompt = prompt.replace(placeholder, value)

        return prompt

    async def _do_call(self, prompt: str):
        """Appel Groq (rejouable par retry)."""
        return await self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            temperature=TDR_TEMPERATURE,
            max_tokens=TDR_MAX_OUTPUT_TOKENS,
            response_format={"type": "json_object"},
        )

    async def generate(self, brief: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Génère un TDR complet à partir du brief."""
        if not brief:
            return None

        prompt = self._build_prompt(brief)
        start = time.perf_counter()

        logger.info("=" * 60)
        logger.info("🚀 M2 TDR — DÉBUT")
        logger.info("📝 Client : %s", brief.get("client", "?"))
        logger.info("=" * 60)

        try:
            response = await retry_with_backoff(
                self._do_call,
                prompt,
                max_retries=3,
                base_delay=2.0,
                retryable_exceptions=(httpx.TimeoutException, httpx.HTTPError),
                label="TDR-Groq",
            )

            elapsed = time.perf_counter() - start
            logger.info("⏱️ Groq : %.2fs", elapsed)

            content = response.choices[0].message.content
            if not content:
                logger.error("❌ TDR : réponse vide")
                return None

            data = self._extract_json(content)
            if not data:
                return None

            data["generation_time_seconds"] = round(elapsed, 2)
            data["ai_provider"] = "groq"
            data["client"] = brief.get("client", "")

            logger.info("✅ TDR généré : '%s'", data.get("titre", "?"))
            return data

        except Exception as exc:
            logger.exception("❌ TDR erreur : %s", exc)
            return None

    @staticmethod
    def _extract_json(content: str) -> Optional[Dict[str, Any]]:
        """Extrait le JSON d'une réponse Groq."""
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            pass

        match = re.search(r"\{[\s\S]*\}", content)
        if match:
            try:
                return json.loads(match.group(0))
            except json.JSONDecodeError:
                pass

        logger.error("❌ Impossible d'extraire le JSON")
        return None