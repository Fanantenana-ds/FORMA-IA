# app/api/v1/routes_tdr.py
# ============================================================
# FORMA-IA — M2 TDR — ROUTES API (V4.0)
# ============================================================

import logging
from pathlib import Path
from typing import List, Dict, Any

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse

from app.schemas.tdr import (
    TDRRequest,
    TDRResponse,
    TDRFiles,
    TDRFromOpportuniteResponse,
)
from app.orchestrator.tdr_orchestrator import TdrOrchestrator
from app.services.backend_sync.opportunity_fetcher import (
    fetch_opportunite_by_id,
    fetch_opportunites_list,
    opportunity_to_brief,
)

logger = logging.getLogger(__name__)
router = APIRouter()
orchestrator = TdrOrchestrator()

BASE_DIR = Path(__file__).resolve().parents[3]
EXPORTS_DIR = BASE_DIR / "exports" / "tdr"


# ============================================================
# 1. GÉNÉRATION TDR (existant)
# ============================================================

@router.post(
    "/ia/tdr/generer",
    response_model=TDRResponse,
    tags=["M2 - TDR"],
    operation_id="genererTDR",
)
async def generer_tdr(request: TDRRequest):
    """Génère un TDR complet à partir d'un brief client."""
    try:
        brief = request.model_dump()
        logger.info("📄 Génération TDR pour : %s", request.client)

        result = await orchestrator.generate(brief)

        if not result.get("success"):
            return TDRResponse(
                success=False, data=None, files=None,
                error=result.get("error", "Erreur inconnue"),
            )

        raw_files = result.get("files") or {}
        files_obj = TDRFiles(
            docx=raw_files.get("docx") or None,
            pdf=raw_files.get("pdf") or None,
        )

        return TDRResponse(
            success=True,
            data=result.get("data"),
            files=files_obj,
            error=None,
        )

    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("❌ Erreur TDR : %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


# ============================================================
# 2. ✅ NOUVEAU : PRÉ-REMPLIR DEPUIS UNE OPPORTUNITÉ
# ============================================================

@router.get(
    "/ia/tdr/from-opportunite/{opportunite_id}",
    response_model=TDRFromOpportuniteResponse,
    tags=["M2 - TDR"],
    operation_id="getTDRBriefFromOpportunite",
)
async def get_brief_from_opportunite(opportunite_id: str):
    """
    Récupère le brief TDR pré-rempli à partir d'une opportunité M1.
    
    Utilisation Frontend :
      1. L'utilisateur clique sur "Générer TDR" pour une opportunité
      2. Appeler cet endpoint avec l'ID de l'opportunité
      3. Recevoir le brief pré-rempli
      4. Compléter les champs manquants (public, durée, lieu)
      5. Appeler POST /ia/tdr/generer avec le brief complet
    """
    try:
        logger.info(
            "📥 Fetch opportunité pour TDR : %s", opportunite_id
        )

        # 1. Récupérer l'opportunité depuis le Backend
        opportunite = await fetch_opportunite_by_id(opportunite_id)

        if not opportunite:
            return TDRFromOpportuniteResponse(
                success=False,
                brief=None,
                opportunite=None,
                error=f"Opportunité introuvable : {opportunite_id}",
            )

        # 2. Convertir en brief TDR
        brief = opportunity_to_brief(opportunite)

        logger.info(
            "✅ Brief TDR pré-rempli pour : %s",
            opportunite.get("objet", "?")[:60]
        )

        return TDRFromOpportuniteResponse(
            success=True,
            brief=brief,
            opportunite=opportunite,
            error=None,
        )

    except Exception as exc:
        logger.exception("❌ Erreur fetch opportunité : %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


# ============================================================
# 3. ✅ NOUVEAU : LISTER LES OPPORTUNITÉS (pour Frontend)
# ============================================================

@router.get(
    "/ia/tdr/opportunites-disponibles",
    tags=["M2 - TDR"],
    operation_id="listOpportunitesForTDR",
)
async def list_opportunites_disponibles(
    limit: int = Query(50, ge=1, le=100),
):
    """
    Liste les opportunités disponibles pour générer un TDR.
    
    Utilisation Frontend :
      1. Afficher la liste des opportunités
      2. L'utilisateur choisit une
      3. Appeler GET /ia/tdr/from-opportunite/{id}
    """
    try:
        opportunites = await fetch_opportunites_list(limit=limit)
        return {
            "success": True,
            "total": len(opportunites),
            "data": opportunites,
        }
    except Exception as exc:
        logger.exception("❌ Erreur list opportunités : %s", exc)
        return {
            "success": False,
            "total": 0,
            "data": [],
            "error": str(exc),
        }


# ============================================================
# 4. TÉLÉCHARGEMENT (existant)
# ============================================================

@router.get(
    "/ia/tdr/download/{filename}",
    tags=["M2 - TDR"],
    operation_id="downloadTDR",
)
async def download_tdr(filename: str):
    """Télécharge un fichier TDR (Word ou PDF)."""
    if ".." in filename or "/" in filename or "\\" in filename:
        raise HTTPException(400, "Nom de fichier invalide")

    file_path = EXPORTS_DIR / filename
    if not file_path.exists() or not file_path.is_file():
        raise HTTPException(404, f"Fichier non trouvé : {filename}")

    if filename.endswith(".docx"):
        media_type = (
            "application/vnd.openxmlformats-officedocument"
            ".wordprocessingml.document"
        )
    elif filename.endswith(".pdf"):
        media_type = "application/pdf"
    else:
        media_type = "application/octet-stream"

    return FileResponse(
        path=str(file_path),
        media_type=media_type,
        filename=filename,
    )


# ============================================================
# 5. LISTE TDR (existant)
# ============================================================

@router.get(
    "/ia/tdr/list",
    tags=["M2 - TDR"],
    operation_id="listTDR",
)
async def list_tdr():
    """Liste tous les TDR générés."""
    try:
        if not EXPORTS_DIR.exists():
            return {"success": True, "data": [], "total": 0}

        files = []
        for f in EXPORTS_DIR.iterdir():
            if f.is_file() and f.suffix in (".docx", ".pdf"):
                files.append({
                    "name": f.name,
                    "size": f.stat().st_size,
                    "modified": f.stat().st_mtime,
                    "type": f.suffix[1:],
                })

        files.sort(key=lambda x: x["modified"], reverse=True)
        return {"success": True, "data": files, "total": len(files)}

    except Exception as exc:
        logger.exception("❌ Erreur liste TDR : %s", exc)
        return {"success": False, "error": str(exc)}