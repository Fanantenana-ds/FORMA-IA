# ============================================================
# FORMA-IA — M1 VEILLE
# ROUTES API
# api/v1/routes_veille.py
# ============================================================
# Version : V2.0 — Seuils permissifs + operation_id explicites
# ============================================================

from __future__ import annotations

import io
import logging
from typing import List, Optional

from fastapi import Depends, Query
from app.utils.security import verify_api_key
from app.services.benchmark.benchmark_runner import BenchmarkRunner

import PyPDF2

from fastapi import (
    APIRouter,
    File,
    Form,
    HTTPException,
    UploadFile,
)
from pydantic import (
    BaseModel,
    Field,
)

from app.orchestrator.veille_orchestrator import (
    VeilleOrchestrator,
)
from app.services.veille import auto_detection_service as auto_detection
from app.services.veille import tavily_quota_service
from app.services.veille.tavily_quota_service import QuotaTavilyDepasseError


logger = logging.getLogger(__name__)

router = APIRouter()
# dependencies=[Depends(verify_api_key)]  # ← décommenter pour activer la protection


# ============================================================
# ORCHESTRATEUR
# ============================================================

orchestrator = VeilleOrchestrator()


# ============================================================
# REQUESTS / RESPONSES
# ============================================================

class SearchRequest(BaseModel):

    query: str = Field(
        ...,
        min_length=2,
        max_length=500,
    )

    domains: Optional[List[str]] = None

    # ✅ Seuil ABAISSÉ pour ne pas filtrer les opportunités valides
    min_score: int = Field(
        default=10,       # était 40
        ge=0,
        le=100,
    )

    limit: int = Field(
        default=20,
        ge=1,
        le=50,
    )


class AnalyseTexteRequest(BaseModel):

    texte: str = Field(
        ...,
        min_length=2,
        max_length=10000,
    )

    source: Optional[str] = "manuel"


class DetectionAutoRequest(BaseModel):
    """Corps OPTIONNEL : sans corps, la configuration VEILLE_AUTO_* s'applique."""

    min_score: Optional[int] = Field(default=None, ge=0, le=100)
    limit: Optional[int] = Field(default=None, ge=1, le=50)
    # False = aperçu : rien n'est envoyé au Backend
    sync_backend: bool = True


class SearchResponse(BaseModel):

    success: bool
    data: dict
    error: Optional[str] = None
    file: Optional[dict] = None


# ============================================================
# NORMALISATION — PERMISSIVE
# ============================================================

def _normalize_result(
    resultat: dict,
    min_score: int,
    limit: int,
):
    """Filtre les opportunités avec un seuil bas pour ne rien manquer."""

    if not isinstance(resultat, dict):
        raise HTTPException(
            status_code=502,
            detail="Réponse invalide de l'orchestrateur.",
        )

    opportunities = resultat.get("opportunities", [])

    if not isinstance(opportunities, list):
        opportunities = []

    filtered = []

    for opportunity in opportunities:

        if not isinstance(opportunity, dict):
            continue

        try:
            score = int(opportunity.get("score", 0))
        except (TypeError, ValueError):
            score = 0

        # ✅ Filtrer UNIQUEMENT si le score est vraiment très bas
        if score < min_score:
            continue

        opportunity["score"] = score

        try:
            opportunity["confidence"] = round(
                float(opportunity.get("confidence", 0)),
                3,
            )
        except (TypeError, ValueError):
            opportunity["confidence"] = 0.0

        filtered.append(opportunity)

    filtered.sort(
        key=lambda x: (
            x.get("score", 0),
            x.get("confidence", 0),
        ),
        reverse=True,
    )

    filtered = filtered[:limit]

    resultat["opportunities"] = filtered
    resultat["total"] = len(filtered)

    return resultat


# ===========================================================
# SYSTÈME
# ===========================================================

@router.post("/benchmark", tags=["Système"])
async def run_benchmark(limit: int = Query(20, ge=1, le=100)):
    runner = BenchmarkRunner()
    report = await runner.run(limit=limit)
    return {"status": "success", "report": report}


# ============================================================
# 1. RECHERCHER
# ============================================================

@router.post(
    "/ia/veille/rechercher",
    response_model=SearchResponse,
    tags=["M1 - Veille Marché"],
    operation_id="rechercherOpportunites",
    summary="Mode 1 — Recherche d'offres (requête saisie)",
)
async def rechercher_opportunites(
    request: SearchRequest,
):

    logger.info(
        "🔍 IA: Recherche: %s...",
        request.query[:100],
    )

    try:

        resultat = await orchestrator.analyser_opportunites(
            query=request.query
        )

        resultat = _normalize_result(
            resultat=resultat,
            min_score=request.min_score,
            limit=request.limit,
        )

        logger.info(
            "✅ IA: %d opportunités retournées",
            resultat.get("total", 0),
        )

        return {
            "success": True,
            "data": resultat,
            "error": None,
        }

    except QuotaTavilyDepasseError as exc:
        raise HTTPException(status_code=429, detail=str(exc))

    except HTTPException:
        raise

    except Exception as exc:

        logger.exception(
            "❌ Erreur recherche M1 : %s",
            exc,
        )

        raise HTTPException(
            status_code=500,
            detail="Erreur interne du service de veille.",
        )


# ============================================================
# 1 bis. DÉTECTION AUTOMATIQUE (sans requête saisie)
# ============================================================

@router.post(
    "/ia/veille/detecter",
    response_model=SearchResponse,
    tags=["M1 - Veille Marché"],
    operation_id="detecterOpportunites",
    summary="Mode 2 — Détection automatique (sans requête)",
)
async def detecter_opportunites(
    request: Optional[DetectionAutoRequest] = None,
):
    """
    Lance les requêtes du profil ALTIORA (VEILLE_AUTO_QUERIES ou défaut),
    fusionne, dédoublonne, garde les meilleurs scores et enregistre dans le
    Backend celles qui n'y sont pas déjà. Peut durer plusieurs dizaines de
    secondes (une recherche + analyse IA par requête).
    """
    request = request or DetectionAutoRequest()

    try:
        resultat = await auto_detection.executer_detection(
            orchestrator,
            declenchement="manuel",
            min_score=request.min_score,
            limit=request.limit,
            sync_backend=request.sync_backend,
        )
        return {"success": True, "data": resultat, "error": None}

    except auto_detection.DetectionAutoEnCours:
        raise HTTPException(
            status_code=409,
            detail="Une détection automatique est déjà en cours.",
        )

    except Exception as exc:
        logger.exception("❌ Erreur détection automatique M1 : %s", exc)
        raise HTTPException(
            status_code=500,
            detail="Erreur interne lors de la détection automatique.",
        )


@router.get(
    "/ia/veille/detecter/statut",
    response_model=SearchResponse,
    tags=["M1 - Veille Marché"],
    operation_id="statutDetectionAutomatique",
    summary="Mode 2 — État et configuration de la détection automatique",
)
async def statut_detection_automatique():
    return {
        "success": True,
        "data": {
            "en_cours": auto_detection.est_en_cours(),
            "configuration": auto_detection.get_config(),
            "derniere_execution": auto_detection.lire_etat() or None,
        },
        "error": None,
    }


@router.get(
    "/ia/veille/quota",
    tags=["M1 - Veille Marché"],
    operation_id="quotaTavily",
    summary="Quota Tavily — appels HTTP réels du mois, par catégorie",
)
async def quota_tavily():
    """
    Appels HTTP RÉELS vers Tavily ce mois-ci (pas les "requêtes"
    utilisateur — jusqu'à 2 appels HTTP par recherche, repli et retries
    compris), ventilés par catégorie (auto / manuel / collecte), restant,
    pourcentage utilisé, configuration active, avertissement (80%/95%).
    """
    return {"success": True, "data": tavily_quota_service.etat_pour_route(), "error": None}


# ============================================================
# 2. ANALYSE TEXTE
# ============================================================

@router.post(
    "/ia/veille/analyser-texte",
    response_model=SearchResponse,
    tags=["M1 - Veille Marché"],
    operation_id="analyserTexte",
)
async def analyser_texte(
    request: AnalyseTexteRequest,
):

    try:

        texte = request.texte.strip()

        if not texte:
            raise HTTPException(
                status_code=400,
                detail="Le texte est vide.",
            )

        result = await orchestrator.analyser_texte(
            texte=texte,
            source=request.source or "manuel",
        )

        return {
            "success": True,
            "data": result,
            "error": None,
        }

    except HTTPException:
        raise

    except Exception as exc:

        logger.exception(
            "❌ Erreur analyse texte : %s",
            exc,
        )

        raise HTTPException(
            status_code=500,
            detail="Erreur interne lors de l'analyse texte.",
        )


# ============================================================
# 3. ANALYSE PDF
# ============================================================

@router.post(
    "/ia/veille/analyser-pdf",
    tags=["M1 - Veille Marché"],
    operation_id="analyserPdf",
)
async def analyser_pdf(
    file: UploadFile = File(...),
    source: str = Form(default="manuel"),
):

    filename = (file.filename or "").lower()

    if not filename.endswith(".pdf"):
        raise HTTPException(
            status_code=400,
            detail="Le fichier doit être un PDF.",
        )

    try:

        contents = await file.read()

        if not contents:
            raise HTTPException(
                status_code=400,
                detail="Le PDF est vide.",
            )

        max_size = 15 * 1024 * 1024

        if len(contents) > max_size:
            raise HTTPException(
                status_code=413,
                detail="PDF trop volumineux (maximum 15 MB).",
            )

        try:
            reader = PyPDF2.PdfReader(io.BytesIO(contents))
        except Exception:
            raise HTTPException(
                status_code=400,
                detail="PDF invalide ou corrompu.",
            )

        pages = []

        for page in reader.pages:
            text = (page.extract_text() or "").strip()
            if text:
                pages.append(text)

        texte_complet = "\n\n".join(pages)

        if not texte_complet.strip():
            raise HTTPException(
                status_code=400,
                detail="Aucun texte exploitable dans le PDF.",
            )

        texte_complet = texte_complet[:10000]

        resultat = await orchestrator.analyser_texte(
            texte=texte_complet,
            source=source,
        )

        return {
            "success": True,
            "data": resultat,
            "error": None,
            "file": {
                "filename": file.filename,
                "content_type": file.content_type,
                "source": source,
                "size_bytes": len(contents),
            },
        }

    except HTTPException:
        raise

    except Exception as exc:

        logger.exception(
            "❌ Erreur PDF : %s",
            exc,
        )

        raise HTTPException(
            status_code=500,
            detail="Erreur interne lors de l'analyse PDF.",
        )