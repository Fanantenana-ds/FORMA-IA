# ============================================================
# FORMA-IA — M1 VEILLE
# ROUTES API
# ============================================================

from __future__ import annotations

import io
import logging
from typing import List, Optional
from fastapi import Depends
from app.utils.security import verify_api_key

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


logger = logging.getLogger(__name__)

router = APIRouter(dependencies=[Depends(verify_api_key)])


# ============================================================
# ORCHESTRATEUR
# ============================================================

orchestrator = VeilleOrchestrator()


# ============================================================
# REQUESTS
# ============================================================

class SearchRequest(BaseModel):

    query: str = Field(
        ...,
        min_length=2,
        max_length=500,
    )

    domains: Optional[List[str]] = None

    min_score: int = Field(
        default=40,
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


class SearchResponse(BaseModel):

    success: bool

    data: dict

    error: Optional[str] = None

    file: Optional[dict] = None


# ============================================================
# NORMALISATION
# ============================================================

def _normalize_result(
    resultat: dict,
    min_score: int,
    limit: int,
):

    if not isinstance(
        resultat,
        dict,
    ):
        raise HTTPException(
            status_code=502,
            detail=(
                "Réponse invalide "
                "de l'orchestrateur."
            ),
        )

    opportunities = resultat.get(
        "opportunities",
        [],
    )

    if not isinstance(
        opportunities,
        list,
    ):
        opportunities = []

    filtered = []

    for opportunity in opportunities:

        if not isinstance(
            opportunity,
            dict,
        ):
            continue

        try:
            score = int(
                opportunity.get(
                    "score",
                    0,
                )
            )
        except (
            TypeError,
            ValueError,
        ):
            score = 0

        if score < min_score:
            continue

        opportunity[
            "score"
        ] = score

        try:
            opportunity[
                "confidence"
            ] = round(
                float(
                    opportunity.get(
                        "confidence",
                        0,
                    )
                ),
                3,
            )
        except (
            TypeError,
            ValueError,
        ):
            opportunity[
                "confidence"
            ] = 0.0

        filtered.append(
            opportunity
        )

    filtered.sort(
        key=lambda x: (
            x.get(
                "score",
                0,
            ),
            x.get(
                "confidence",
                0,
            ),
        ),
        reverse=True,
    )

    filtered = filtered[:limit]

    resultat[
        "opportunities"
    ] = filtered

    resultat[
        "total"
    ] = len(filtered)

    return resultat


# ============================================================
# 1. RECHERCHER
# ============================================================

@router.post(
    "/ia/veille/rechercher",
    response_model=SearchResponse,
    tags=["M1 - Veille Marché"],
)
async def rechercher_opportunites(
    request: SearchRequest,
):

    logger.info(
        "🔍 IA: Recherche: %s...",
        request.query[:100],
    )

    try:

        resultat = (
            await orchestrator.analyser_opportunites(
                query=request.query
            )
        )

        resultat = _normalize_result(
            resultat=resultat,
            min_score=request.min_score,
            limit=request.limit,
        )

        logger.info(
            "✅ IA: %d opportunités retournées",
            resultat.get(
                "total",
                0,
            ),
        )

        return {
            "success": True,
            "data": resultat,
            "error": None,
        }

    except HTTPException:
        raise

    except Exception as exc:

        logger.exception(
            "❌ Erreur recherche M1 : %s",
            exc,
        )

        raise HTTPException(
            status_code=500,
            detail=(
                "Erreur interne du "
                "service de veille."
            ),
        )


# ============================================================
# 2. ANALYSE TEXTE
# ============================================================

@router.post(
    "/ia/veille/analyser-texte",
    response_model=SearchResponse,
    tags=["M1 - Veille Marché"],
)
async def analyser_texte(
    request: AnalyseTexteRequest,
):

    try:

        texte = request.texte.strip()

        result = await orchestrator.analyser_texte(request.texte, request.source)

        return {
            "success": True,
            "data": result,
            "error": None,
        }

    except Exception as exc:

        logger.exception(
            "❌ Erreur analyse texte : %s",
            exc,
        )

        raise HTTPException(
            status_code=500,
            detail=(
                "Erreur interne lors "
                "de l'analyse texte."
            ),
        )


# ============================================================
# 3. ANALYSE PDF
# ============================================================

@router.post(
    "/ia/veille/analyser-pdf",
    tags=["M1 - Veille Marché"],
)
async def analyser_pdf(
    file: UploadFile = File(...),
    source: str = Form(
        default="manuel"
    ),
):

    filename = (
        file.filename or ""
    ).lower()

    if not filename.endswith(
        ".pdf"
    ):
        raise HTTPException(
            status_code=400,
            detail=(
                "Le fichier doit être "
                "un PDF."
            ),
        )

    try:

        contents = await file.read()

        if not contents:

            raise HTTPException(
                status_code=400,
                detail=(
                    "Le PDF est vide."
                ),
            )

        max_size = (
            15 * 1024 * 1024
        )

        if len(contents) > max_size:

            raise HTTPException(
                status_code=413,
                detail=(
                    "PDF trop volumineux "
                    "(maximum 15 MB)."
                ),
            )

        try:

            reader = PyPDF2.PdfReader(
                io.BytesIO(contents)
            )

        except Exception:

            raise HTTPException(
                status_code=400,
                detail=(
                    "PDF invalide ou "
                    "corrompu."
                ),
            )

        pages = []

        for page in reader.pages:

            text = (
                page.extract_text()
                or ""
            ).strip()

            if text:
                pages.append(
                    text
                )

        texte_complet = (
            "\n\n".join(pages)
        )

        if not texte_complet.strip():

            raise HTTPException(
                status_code=400,
                detail=(
                    "Aucun texte exploitable "
                    "dans le PDF."
                ),
            )

        texte_complet = (
            texte_complet[:10000]
        )

        resultat = (
            await orchestrator.analyser_texte(
                texte=texte_complet,
                source=source,
            )
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
            detail=(
                "Erreur interne lors "
                "de l'analyse PDF."
            ),
        )
from fastapi import Query
from app.services.benchmark.benchmark_runner import BenchmarkRunner

@router.post("/benchmark")
async def run_benchmark(limit: int = Query(20, ge=1, le=100)):
    runner = BenchmarkRunner()
    report = await runner.run(limit=limit)
    return {"status": "success", "report": report}