# ============================================================
# ROUTES API — M1 VEILLE MARCHÉ (AVEC GROQ)
# ============================================================

from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from pydantic import BaseModel
from typing import Optional, List
import io
import PyPDF2
import logging

from app.orchestrator.veille_orchestrator import VeilleOrchestrator

logger = logging.getLogger(__name__)

router = APIRouter()
orchestrator = VeilleOrchestrator()

# ============================================================
# SCHÉMAS PYDANTIC
# ============================================================

class SearchRequest(BaseModel):
    query: str
    domains: Optional[List[str]] = None
    min_score: Optional[int] = 60
    limit: Optional[int] = 20

class AnalyseTexteRequest(BaseModel):
    texte: str
    source: Optional[str] = "manuel"

class SearchResponse(BaseModel):
    success: bool
    data: dict
    error: Optional[str] = None

# ============================================================
# ENDPOINTS M1
# ============================================================

@router.post("/ia/veille/rechercher", response_model=SearchResponse, tags=["M1 - Veille Marché"])
async def rechercher_opportunites(request: SearchRequest):
    """
    Recherche et analyse des opportunités commerciales via Tavily + Groq.

    - **query**: La requête de recherche (ex: "formation IA Madagascar")
    - **domains**: Filtrer par domaine (ia, devops, data, etc.)
    - **min_score**: Score minimum de pertinence (0-100)
    - **limit**: Nombre maximum de résultats
    """
    logger.info(f"🔍 Recherche: {request.query}")
    try:
        resultat = orchestrator.analyser_opportunites(request.query)
        logger.info(f"✅ Résultat: {resultat.get('data', {}).get('total', 0)} opportunités trouvées")
        return resultat
    except Exception as e:
        logger.error(f"❌ Erreur: {e}")
        return {
            "success": False,
            "data": {},
            "error": str(e)
        }

@router.post("/ia/veille/analyser-texte", response_model=SearchResponse, tags=["M1 - Veille Marché"])
async def analyser_texte(request: AnalyseTexteRequest):
    """
    Analyse un texte d'appel d'offres copié-collé.
    """
    try:
        resultat = orchestrator.analyser_opportunites(request.texte[:1000])
        return resultat
    except Exception as e:
        return {
            "success": False,
            "data": {},
            "error": str(e)
        }

@router.post("/ia/veille/analyser-pdf", tags=["M1 - Veille Marché"])
async def analyser_pdf(
    file: UploadFile = File(...),
    source: str = Form("manuel")
):
    """
    Analyse un fichier PDF d'appel d'offres.
    """
    if not file.filename.endswith('.pdf'):
        raise HTTPException(400, "Le fichier doit être un PDF")

    try:
        contents = await file.read()
        pdf_reader = PyPDF2.PdfReader(io.BytesIO(contents))

        texte_complet = ""
        for page in pdf_reader.pages:
            texte_complet += page.extract_text()

        if not texte_complet.strip():
            raise HTTPException(400, "Le PDF est vide")

        resultat = orchestrator.analyser_opportunites(texte_complet[:1000])
        return resultat

    except Exception as e:
        raise HTTPException(500, f"Erreur : {str(e)}")

@router.get("/ia/veille/opportunites", tags=["M1 - Veille Marché"])
async def list_opportunites(
    domain: Optional[str] = None,
    min_score: Optional[int] = None,
    limit: int = 50
):
    """
    Liste toutes les opportunités analysées.
    """
    return {
        "opportunities": [],
        "total": 0,
        "filters": {
            "domain": domain,
            "min_score": min_score,
            "limit": limit
        }
    }

@router.get("/ia/veille/opportunites/{id}", tags=["M1 - Veille Marché"])
async def get_opportunite(id: int):
    """
    Récupère une opportunité par son ID.
    """
    return {
        "id": id,
        "message": "Opportunité à récupérer depuis la base"
    }








# # ============================================================
# # ROUTES API — M1 VEILLE MARCHÉ
# # ============================================================

# from fastapi import APIRouter, HTTPException, UploadFile, File, Form
# from pydantic import BaseModel
# from typing import Optional, List
# import io
# import PyPDF2

# from app.orchestrator.veille_orchestrator import VeilleOrchestrator

# # Créer le router
# router = APIRouter()
# orchestrator = VeilleOrchestrator()

# # ============================================================
# # SCHÉMAS PYDANTIC
# # ============================================================

# class SearchRequest(BaseModel):
#     query: str
#     domains: Optional[List[str]] = None
#     min_score: Optional[int] = 60
#     limit: Optional[int] = 20

# class AnalyseTexteRequest(BaseModel):
#     texte: str
#     source: Optional[str] = "manuel"

# class SearchResponse(BaseModel):
#     success: bool
#     data: dict
#     error: Optional[str] = None

# # ============================================================
# # ENDPOINTS M1
# # ============================================================

# @router.post("/ia/veille/rechercher", response_model=SearchResponse, tags=["M1 - Veille Marché"])
# async def rechercher_opportunites(request: SearchRequest):
#     """
#     Recherche et analyse des opportunités commerciales via Tavily.

#     - **query**: La requête de recherche (ex: "formation IA Madagascar")
#     - **domains**: Filtrer par domaine (ia, devops, data, etc.)
#     - **min_score**: Score minimum de pertinence (0-100)
#     - **limit**: Nombre maximum de résultats
#     """
#     try:
#         resultat = orchestrator.analyser_opportunites(request.query)
#         return resultat
#     except Exception as e:
#         return {
#             "success": False,
#             "data": {},
#             "error": str(e)
#         }

# @router.post("/ia/veille/analyser-texte", response_model=SearchResponse, tags=["M1 - Veille Marché"])
# async def analyser_texte(request: AnalyseTexteRequest):
#     """
#     Analyse un texte d'appel d'offres copié-collé.

#     - **texte**: Le contenu de l'appel d'offres
#     - **source**: La source du texte (manuel, email, etc.)
#     """
#     try:
#         resultat = orchestrator.analyser_opportunites(request.texte[:1000])
#         return resultat
#     except Exception as e:
#         return {
#             "success": False,
#             "data": {},
#             "error": str(e)
#         }

# @router.post("/ia/veille/analyser-pdf", tags=["M1 - Veille Marché"])
# async def analyser_pdf(
#     file: UploadFile = File(...),
#     source: str = Form("manuel")
# ):
#     """
#     Analyse un fichier PDF d'appel d'offres.

#     - **file**: Le fichier PDF à analyser
#     - **source**: La source du document
#     """
#     if not file.filename.endswith('.pdf'):
#         raise HTTPException(400, "Le fichier doit être un PDF")

#     try:
#         contents = await file.read()
#         pdf_reader = PyPDF2.PdfReader(io.BytesIO(contents))

#         texte_complet = ""
#         for page in pdf_reader.pages:
#             texte_complet += page.extract_text()

#         if not texte_complet.strip():
#             raise HTTPException(400, "Le PDF est vide")

#         resultat = orchestrator.analyser_opportunites(texte_complet[:1000])
#         return resultat

#     except Exception as e:
#         raise HTTPException(500, f"Erreur : {str(e)}")

# @router.get("/ia/veille/opportunites", tags=["M1 - Veille Marché"])
# async def list_opportunites(
#     domain: Optional[str] = None,
#     min_score: Optional[int] = None,
#     limit: int = 50
# ):
#     """
#     Liste toutes les opportunités analysées.

#     - **domain**: Filtrer par domaine (ia, devops, data, etc.)
#     - **min_score**: Score minimum de pertinence
#     - **limit**: Nombre maximum de résultats
#     """
#     return {
#         "opportunities": [],
#         "total": 0,
#         "filters": {
#             "domain": domain,
#             "min_score": min_score,
#             "limit": limit
#         }
#     }

# @router.get("/ia/veille/opportunites/{id}", tags=["M1 - Veille Marché"])
# async def get_opportunite(id: int):
#     """
#     Récupère une opportunité par son ID.
#     """
#     return {
#         "id": id,
#         "message": "Opportunité à récupérer depuis la base"
#     }