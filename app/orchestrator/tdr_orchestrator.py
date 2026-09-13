# app/orchestrator/tdr_orchestrator.py
# ============================================================
# FORMA-IA — M2 TDR — ORCHESTRATEUR
# ============================================================
# Version : V2.0 — Ajout sync Backend
# ============================================================

import logging
from typing import Any, Dict, Optional

from app.services.tdr.tdr_service import TDRService
from app.services.tdr.tdr_document_generator import TDRDocumentGenerator
from app.services.backend_sync.tdr_sync import sync_tdr_to_backend

logger = logging.getLogger(__name__)


class TdrOrchestrator:
    """Orchestrateur M2 — coordonne service IA + générateur + sync."""

    def __init__(self):
        self.tdr_service = TDRService()
        self.document_generator = TDRDocumentGenerator()

    async def generate(self, brief: Dict[str, Any]) -> Dict[str, Any]:
        """Pipeline complet : brief → TDR JSON → Word → PDF → Backend."""

        # 1. Génération IA
        tdr_content = await self.tdr_service.generate(brief)

        if not tdr_content:
            return {
                "success": False,
                "error": "Échec de la génération IA",
                "data": None,
                "files": None,
            }

        # 2. Génération documents
        docx_filename, pdf_filename = self.document_generator.generate(
            tdr_content=tdr_content,
            client=brief.get("client", "Client"),
        )

        # 3. ✅ SYNC BACKEND (optionnel, non bloquant)
        opportunite_id = brief.get("opportunite_id")
        sync_result = await sync_tdr_to_backend(
            tdr_content=tdr_content,
            docx_filename=docx_filename,
            pdf_filename=pdf_filename,
            opportunite_id=opportunite_id,
        )

        # Ajouter le résultat de sync dans les données
        tdr_content["backend_sync"] = sync_result

        return {
            "success": True,
            "data": tdr_content,
            "files": {
                "docx": docx_filename,
                "pdf": pdf_filename,
            },
            "error": None,
        }