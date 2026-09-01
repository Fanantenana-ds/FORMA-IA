# ============================================================
# ROUTES API — M2 TDR
# ============================================================

from fastapi import APIRouter, HTTPException, File, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import Optional, Dict, Any
import os
import logging

from app.orchestrator.tdr_orchestrator import TdrOrchestrator

logger = logging.getLogger(__name__)

router = APIRouter()
orchestrator = TdrOrchestrator()


# ============================================================
# SCHÉMAS PYDANTIC
# ============================================================

class TDRRequest(BaseModel):
    client: str
    objectifs: str
    public: str
    duree: str
    format: Optional[str] = "Présentiel"
    budget: Optional[str] = None


class TDRResponse(BaseModel):
    success: bool
    data: Dict[str, Any]
    error: Optional[str] = None


# ============================================================
# ENDPOINTS
# ============================================================

@router.post("/ia/tdr/generer", response_model=TDRResponse, tags=["M2 - TDR"])
async def generer_tdr(request: TDRRequest):
    """
    Génère un TDR complet à partir d'un brief client.

    - **client**: Nom du client
    - **objectifs**: Objectifs de la formation
    - **public**: Public cible
    - **duree**: Durée de la formation
    - **format**: Format (Présentiel, Distanciel, Mixte)
    - **budget**: Budget estimé (optionnel)

    Retourne le TDR généré avec les documents Word et PDF.
    """
    logger.info(f"📄 Génération TDR pour: {request.client}")

    brief = request.model_dump()
    resultat = orchestrator.generer_tdr(brief)

    if resultat.get("success"):
        logger.info(f"✅ TDR généré avec succès pour: {request.client}")
    else:
        logger.error(f"❌ Erreur TDR: {resultat.get('error')}")

    return resultat


@router.get("/ia/tdr/download/{filename}", tags=["M2 - TDR"])
async def download_tdr(filename: str):
    """
    Télécharge un fichier TDR (Word ou PDF).

    - **filename**: Nom du fichier à télécharger
    """
    file_path = os.path.join("exports/tdr", filename)

    if not os.path.exists(file_path):
        raise HTTPException(404, f"Fichier {filename} non trouvé")

    # Déterminer le type MIME
    if filename.endswith('.docx'):
        media_type = 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
    elif filename.endswith('.pdf'):
        media_type = 'application/pdf'
    else:
        media_type = 'application/octet-stream'

    return FileResponse(
        file_path,
        media_type=media_type,
        filename=filename
    )


@router.get("/ia/tdr/list", tags=["M2 - TDR"])
async def list_tdr():
    """
    Liste tous les TDR générés.
    """
    try:
        files = []
        for f in os.listdir("exports/tdr"):
            if f.endswith('.docx') or f.endswith('.pdf'):
                file_path = os.path.join("exports/tdr", f)
                files.append({
                    "name": f,
                    "size": os.path.getsize(file_path),
                    "modified": os.path.getmtime(file_path)
                })
        return {"success": True, "data": files}
    except Exception as e:
        return {"success": False, "error": str(e)}