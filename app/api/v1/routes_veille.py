# ============================================================
# FORMA-IA — M1 VEILLE
# ROUTES API
# api/v1/routes_veille.py
# ============================================================
# Version : V2.0 — Seuils permissifs + operation_id explicites
# ============================================================

from __future__ import annotations

import asyncio
import io
import json
import logging

import pypdf
from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    UploadFile,
)
from fastapi.responses import StreamingResponse
from pydantic import (
    BaseModel,
    Field,
)

from app.orchestrator.veille_orchestrator import (
    VeilleOrchestrator,
)
from app.services.benchmark.benchmark_runner import BenchmarkRunner
from app.services.veille import auto_detection_service as auto_detection
from app.services.veille import tavily_quota_service
from app.services.veille.demo_mode_service import (
    DEMO_MODE,
    generer_opportunites_demo,
)
from app.services.veille.tavily_quota_service import QuotaTavilyDepasseError
from app.utils.security import verify_api_key

logger = logging.getLogger(__name__)

router = APIRouter(dependencies=[Depends(verify_api_key)])


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

    domains: list[str] | None = None

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

    source: str | None = "manuel"


class DetectionAutoRequest(BaseModel):
    """Corps OPTIONNEL : sans corps, la configuration VEILLE_AUTO_* s'applique."""

    min_score: int | None = Field(default=None, ge=0, le=100)
    limit: int | None = Field(default=None, ge=1, le=50)
    # False = aperçu : rien n'est envoyé au Backend
    sync_backend: bool = True


class SearchResponse(BaseModel):

    success: bool
    data: dict
    error: str | None = None
    file: dict | None = None


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
    request: DetectionAutoRequest | None = None,
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
            sync_backend=False,
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
            reader = pypdf.PdfReader(io.BytesIO(contents))
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
            sync_backend=False,
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


# ============================================================
# 4. SYNCHRONISATION BACKEND — APRÈS APPROBATION HITL
# ============================================================

class SynchroniserBackendRequest(BaseModel):
    review_id: str
    force: bool = False


@router.post(
    "/ia/veille/synchroniser-backend",
    response_model=SearchResponse,
    tags=["M1 - Veille Marché"],
    operation_id="synchroniserBackendVeille",
    summary="Sync M1 → Backend après approbation HITL (agent_m1_veille)",
    description=(
        "Envoie les opportunités approuvées au Backend.\n\n"
        "⚠️ Requiert une review HITL approuvée (agent_m1_veille). "
        "Sans approbation humaine, la requête est rejetée (403)."
    ),
)
async def synchroniser_backend(
    request: SynchroniserBackendRequest,
):
    try:
        result = await orchestrator.synchroniser_backend(
            review_id=request.review_id,
            force=request.force,
        )
        return {"success": True, "data": result, "error": None}
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except Exception as exc:
        logger.exception("❌ Erreur sync veille Backend : %s", exc)
        raise HTTPException(
            status_code=500,
            detail="Erreur interne lors de la synchronisation Backend.",
        )


# ============================================================
# DÉTECTION EN STREAMING (Server-Sent Events)
# ============================================================

def _sse(event: str, data: dict) -> str:
    """Formate un événement SSE."""
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


async def _stream_detection(min_score: int, limit: int, sync_backend: bool):
    """
    Générateur SSE — émet les événements de détection en temps réel.

    DEMO_MODE=true : joue directement le Plan B avec timing simulé (~15s).
    DEMO_MODE=false : lance la vraie détection Tavily + Groq (~3-4 min).
    """
    yield _sse("debut", {
        "message": "Lancement de la détection automatique des opportunités...",
        "demo_mode": DEMO_MODE,
    })
    await asyncio.sleep(0.3)

    # ================================================================
    # BRANCHE DEMO — Plan B complet, sans appel Tavily ni Groq
    # ================================================================
    if DEMO_MODE:
        queries = auto_detection.get_config().get("queries", [])
        total_queries = len(queries)

        # Simuler les requêtes avec timing réaliste
        rejets_simules = [
            "page de liste sans annonce précise",
            "contenu éducatif générique",
            "offre d'emploi CDI, pas de prestation",
            "hors domaine : formation santé",
            "appel d'offres expiré en 2024",
            "rapport d'activité, pas d'appel d'offres",
            "page de portail sans annonce identifiée",
            "hors zone : Douala, Cameroun",
            "liste de marchés sans offre précise",
            "document de procédure administrative",
        ]

        for i, query in enumerate(queries, 1):
            yield _sse("requete", {
                "numero": i,
                "total": total_queries,
                "query": query,
                "message": f"🔍 Requête {i}/{total_queries} : « {query} »",
            })
            await asyncio.sleep(0.8)

            # Émettre 2-3 rejets simulés par requête
            import random
            nb_rejets = random.randint(2, 3)
            for raison in random.sample(rejets_simules, nb_rejets):
                yield _sse("rejet", {
                    "raison": raison,
                    "message": f"❌ Rejeté : {raison}",
                })
                await asyncio.sleep(0.25)

        yield _sse("analyse", {"message": "🧠 Analyse IA — classification et scoring..."})
        await asyncio.sleep(1.2)

        # Opportunités Plan B
        demo_opps = generer_opportunites_demo(nb_min=3, nb_max=5)
        sources_sim = total_queries * 8
        rejets_sim = sources_sim - len(demo_opps)

        for opp in demo_opps:
            yield _sse("opportunite", {
                "titre": opp.get("title", ""),
                "organizer": opp.get("organizer", ""),
                "score": opp.get("score", 0),
                "confidence": opp.get("confidence", 0),
                "domain": opp.get("domain", ""),
                "budget": opp.get("budget", "Non précisé"),
                "deadline": opp.get("deadline"),
                "summary": opp.get("summary", ""),
                "message": f"✅ {opp.get('title', '')} — score {opp.get('score', 0)}/100",
            })
            await asyncio.sleep(0.6)

        yield _sse("fin", {
            "total": len(demo_opps),
            "sources": sources_sim,
            "rejets": rejets_sim,
            "demo": True,
            "message": (
                f"🎯 Détection terminée : {len(demo_opps)} opportunité(s) retenue(s) "
                f"sur {sources_sim} sources analysées."
            ),
            "opportunites": demo_opps,
        })
        return

    # ================================================================
    # BRANCHE RÉELLE — Tavily + Groq
    # ================================================================
    opportunites_trouvees: list[dict] = []
    sources_analysees = 0
    rejets = 0

    try:
        if tavily_quota_service.quota_depasse():
            yield _sse("erreur", {"message": "Quota Tavily journalier atteint."})
            yield _sse("fin", {"total": 0, "sources": 0, "rejets": 0, "demo": False})
            return

        queries = auto_detection.get_config().get("queries", [])
        total_queries = len(queries)

        for i, query in enumerate(queries, 1):
            yield _sse("requete", {
                "numero": i,
                "total": total_queries,
                "query": query,
                "message": f"🔍 Requête {i}/{total_queries} : « {query} »",
            })
            await asyncio.sleep(0.05)

        yield _sse("analyse", {"message": "🧠 Analyse IA en cours (peut durer 2-3 minutes)..."})

        resultat = await auto_detection.executer_detection(
            orchestrator,
            declenchement="manuel",
            min_score=min_score,
            limit=limit,
            sync_backend=sync_backend,
        )

        opportunites_brutes = resultat.get("opportunites", []) or []
        sources_analysees = resultat.get("sources_analysees", len(opportunites_brutes))
        rejets = resultat.get("rejets", 0)

        for opp in opportunites_brutes:
            opportunites_trouvees.append(opp)
            yield _sse("opportunite", {
                "titre": opp.get("title", ""),
                "organizer": opp.get("organizer", ""),
                "score": opp.get("score", 0),
                "confidence": opp.get("confidence", 0),
                "domain": opp.get("domain", ""),
                "budget": opp.get("budget", "Non précisé"),
                "deadline": opp.get("deadline"),
                "summary": opp.get("summary", ""),
                "message": f"✅ {opp.get('title', '')} — score {opp.get('score', 0)}/100",
            })
            await asyncio.sleep(0.15)

        yield _sse("rejet_info", {
            "message": f"❌ {rejets} sources rejetées (hors domaine, hors zone, contenu informatif…)",
            "rejets": rejets,
        })

        yield _sse("fin", {
            "total": len(opportunites_trouvees),
            "sources": sources_analysees,
            "rejets": rejets,
            "demo": False,
            "message": (
                f"🎯 Détection terminée : {len(opportunites_trouvees)} opportunité(s) "
                f"retenue(s) sur {sources_analysees} sources analysées."
            ),
            "opportunites": opportunites_trouvees,
        })

    except auto_detection.DetectionAutoEnCours:
        yield _sse("erreur", {"message": "Une détection est déjà en cours. Réessayez dans quelques instants."})
        yield _sse("fin", {"total": 0, "sources": 0, "rejets": 0, "demo": False})
    except Exception as exc:
        logger.exception("❌ Erreur stream détection M1 : %s", exc)
        yield _sse("erreur", {"message": "Erreur interne lors de la détection."})
        yield _sse("fin", {"total": 0, "sources": 0, "rejets": 0, "demo": False})


@router.get(
    "/ia/veille/detecter/stream",
    tags=["M1 - Veille Marché"],
    operation_id="streamDetectionOpportunites",
    summary="Mode 2 — Détection automatique en streaming (Server-Sent Events)",
    description=(
        "Lance la détection automatique et émet les résultats en temps réel "
        "via Server-Sent Events. Événements : debut, requete, analyse, "
        "opportunite, plan_b, rejet_info, avertissement, erreur, fin.\n\n"
        "Si DEMO_MODE=true dans .env et que 0 résultat réel est trouvé, "
        "le Plan B injecte des opportunités de démonstration."
    ),
)
async def stream_detection(
    min_score: int = Query(default=40, ge=0, le=100),
    limit: int = Query(default=20, ge=1, le=100),
    sync_backend: bool = Query(default=True),
):
    return StreamingResponse(
        _stream_detection(min_score=min_score, limit=limit, sync_backend=sync_backend),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )