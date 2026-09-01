# ============================================================
# ORCHESTRATEUR M2 — TDR (AVEC OPENROUTER)
# ============================================================

import json
import logging
from typing import Dict, Any

from openai import OpenAI

from app.config.settings import settings
from app.services.generator.word_generator import WordGenerator
from app.services.generator.pdf_generator import PDFGenerator

logger = logging.getLogger(__name__)


class TdrOrchestrator:
    """Orchestrateur M2 — TDR (OpenRouter)"""

    def __init__(self):
        if not settings.OPENROUTER_API_KEY:
            raise ValueError("❌ OPENROUTER_API_KEY non configurée")

        self.client = OpenAI(
            api_key=settings.OPENROUTER_API_KEY,
            base_url="https://openrouter.ai/api/v1"
        )
        self.model = settings.OPENROUTER_MODEL

        self.word_generator = WordGenerator()
        self.pdf_generator = PDFGenerator()

        logger.info(f"✅ M2: Modèle OpenRouter: {self.model}")

    def generer_tdr(self, brief: Dict[str, Any]) -> Dict[str, Any]:
        # ... (mitovy amin'ny teo aloha, fa tsy mampiasa Groq)
        pass