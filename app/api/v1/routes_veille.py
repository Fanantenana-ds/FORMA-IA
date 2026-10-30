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
from contextlib import suppress

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
from fastapi.responses import JSONResponse
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
from app.services.veille.progress_service import PROGRESS_CALLBACK
from app.services.veille.demo_mode_service import (
    DEMO_MODE,
    charger_opportunites_demo_reelles,
    generer_opportunites_demo,
)
from app.services.veille.tavily_quota_service import QuotaTavilyDepasseError
from app.services.veille.access_service import verify_api_key, verify_api_key_sse

logger = logging.getLogger(__name__)

router = APIRouter(dependencies=[Depends(verify_api_key)])

# Router séparé pour les routes SSE : l'auth Bearer standard est incompatible
# avec EventSource (le navigateur ne peut pas envoyer de headers custom).
# verify_api_key_sse accepte le token en query param ?token= ou en header Bearer.
sse_router = APIRouter(dependencies=[Depends(verify_api_key_sse)])


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

        if resultat.get("status") in {"technical_error", "quota_atteint"}:
            return JSONResponse(
                status_code=429 if resultat["status"] == "quota_atteint" else 503,
                content={
                    "success": False,
                    "data": resultat,
                    "error": "La recherche web est temporairement indisponible.",
                },
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
        if resultat.get("status") in {"technical_error", "quota_atteint"}:
            return JSONResponse(
                status_code=429 if resultat["status"] == "quota_atteint" else 503,
                content={"success": False, "data": resultat,
                         "error": resultat.get("notes") or "Détection réelle indisponible."},
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


async def _stream_detection(min_score: int, limit: int, sync_backend: bool, owner: str = "internal"):
    """
    Générateur SSE — émet les événements de détection en temps réel.

    En mode DEMO_MODE=true : rejoue les avis archivés (données réelles capturées)
    avec les mêmes événements et le même rythme que la détection live,
    sans appel Tavily ni Groq.
    En mode normal : détection réelle Tavily + Groq.
    """
    queries = auto_detection.get_config().get("requetes", [])
    total_queries = len(queries)

    yield _sse("debut", {"message": "Lancement de la recherche réelle d’opportunités..."})
    await asyncio.sleep(0.3)

    # ================================================================
    # BRANCHE DEMO — archive réelle, même rythme que le pipeline live
    # ================================================================
    if DEMO_MODE:
        # 1. Affiche les requêtes du profil ALTIORA comme si elles étaient lancées
        for i, query in enumerate(queries, 1):
            yield _sse("requete", {
                "numero": i,
                "total": total_queries,
                "query": query,
                "message": f"🔍 Requête {i}/{total_queries} : « {query} »",
            })
            await asyncio.sleep(0.7)

        # 2. Signal analyse IA (même message que le vrai pipeline)
        yield _sse("analyse", {"message": "🧠 Analyse IA en cours..."})
        await asyncio.sleep(3.5)

        # 3. Charge l'archive réelle ; bascule sur le pool fictif si vide
        opportunites = charger_opportunites_demo_reelles()
        if not opportunites:
            opportunites = generer_opportunites_demo(nb_min=3, nb_max=5)

        # Filtre : score suffisant ET avis encore ouvert (is_actionable)
        # Les avis clôturés sont comptés comme rejetés — réaliste (M1 ne présente que les opportunités actives)
        opportunites_filtrees = [
            o for o in opportunites
            if (o.get("score") or 0) >= min_score and o.get("is_actionable", True)
        ][:limit]

        rejets = len(opportunites) - len(opportunites_filtrees)

        # 4. Stream les résultats un par un
        for opp in opportunites_filtrees:
            yield _sse("opportunite", {
                "titre": opp.get("title", ""),
                "organizer": opp.get("organizer", ""),
                "score": opp.get("score", 0),
                "confidence": opp.get("confidence", 0.85),
                "domain": opp.get("domain", ""),
                "budget": opp.get("budget") or "Non précisé",
                "deadline": opp.get("deadline") or opp.get("date_limite"),
                "summary": opp.get("summary", ""),
                "source_url": opp.get("source_url") or opp.get("url"),
                "reference": opp.get("reference"),
                "current_status": opp.get("current_status", ""),
                "message": f"✅ {opp.get('title', '')} — score {opp.get('score', 0)}/100",
            })
            await asyncio.sleep(0.8)

        yield _sse("rejet_info", {
            "message": f"❌ {rejets} opportunités écartées sous le seuil de score.",
            "rejets": rejets,
        })
        yield _sse("fin", {
            "status": "success",
            "total": len(opportunites_filtrees),
            "sources": total_queries,
            "candidats_collectes": len(opportunites),
            "requêtes": total_queries,
            "rejets": rejets,
            "message": (
                f"🎯 Détection terminée : {len(opportunites_filtrees)} opportunité(s) "
                f"retenue(s) après {total_queries} requête(s), "
                f"{rejets} écartée(s) sous le seuil de score."
            ),
            "opportunites": opportunites_filtrees,
        })
        return

    # ================================================================
    # BRANCHE RÉELLE — Tavily + Groq
    # ================================================================
    opportunites_trouvees: list[dict] = []
    sources_analysees: int | None = None
    rejets = 0

    try:
        if tavily_quota_service.plafond_dur_atteint():
            yield _sse("erreur", {"message": "Plafond Tavily atteint."})
            yield _sse("fin", {"status": "quota_atteint", "total": 0, "sources": 0, "rejets": 0})
            return

        queue = asyncio.Queue(maxsize=128)
        async def progress(event, data):
            await queue.put((event, data))
        async def run_detection():
            token = PROGRESS_CALLBACK.set(progress)
            try:
                return await auto_detection.executer_detection(
                    orchestrator, declenchement="manuel", min_score=min_score,
                    limit=limit, sync_backend=sync_backend)
            finally:
                PROGRESS_CALLBACK.reset(token)
        worker = asyncio.create_task(run_detection())
        received = None
        try:
            while not worker.done() or not queue.empty():
                if not queue.empty():
                    event, data = queue.get_nowait()
                    yield _sse(event, data)
                    continue
                received = asyncio.create_task(queue.get())
                ready, _ = await asyncio.wait({worker, received}, timeout=10, return_when=asyncio.FIRST_COMPLETED)
                if received in ready:
                    event, data = received.result()
                    yield _sse(event, data)
                else:
                    received.cancel()
                    with suppress(asyncio.CancelledError):
                        await received
                    if not worker.done():
                        yield ": keep-alive\n\n"
                received = None
            resultat = await worker
        finally:
            if received is not None and not received.done():
                received.cancel()
                with suppress(asyncio.CancelledError):
                    await received
            if not worker.done():
                worker.cancel()
            with suppress(asyncio.CancelledError):
                await worker

        from app.services.veille.pending_service import bind
        bind(resultat.get("continuation_id"), owner, min_score)
        from app.services.veille.result_context_service import remember
        remember(owner, resultat)
        opportunites_brutes = sorted(resultat.get("opportunities", []) or [], key=lambda o: o.get("score", 0), reverse=True)
        statistiques = resultat.get("statistics") or {}
        sources_analysees = statistiques.get("sources_analyzed")
        rejets = statistiques.get("below_min_score", 0)
        statut = resultat.get("status", "technical_error")

        if statut == "partial":
            yield _sse("analyse", {"stage": "partial_completion", "message": resultat.get("notes") or "Résultats disponibles ; analyse partielle.", "status": statut})
        if statut in {"technical_error", "degraded", "error", "quota_atteint"}:
            yield _sse("erreur", {
                "message": resultat.get("notes") or "La détection n'a pas abouti complètement.",
                "status": statut,
            })

        opportunites_trouvees.extend(opportunites_brutes)
        # Le frontend existant ajoute chaque carte en tête : le meilleur arrive
        # en dernier pour être affiché en premier. Le paquet fin reste décroissant.
        for opp in reversed(opportunites_brutes):
            yield _sse("opportunite", {
                **opp,
                "rank": opportunites_brutes.index(opp) + 1,
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

        for candidate in resultat.get("to_review_candidates", []):
            yield _sse("candidat_a_verifier", candidate)

        yield _sse("rejet_info", {
            "message": f"❌ {rejets} opportunités écartées sous le seuil de score.",
            "rejets": rejets,
        })

        yield _sse("fin", {
            "status": statut,
            "total": len(opportunites_trouvees),
            "sources": sources_analysees,
            "candidats_collectes": statistiques.get("raw_results", statistiques.get("collected", 0)),
            "requêtes": statistiques.get("queries_run", len(queries)),
            "rejets": rejets,
            "message": (
                f"🎯 Détection terminée : {len(opportunites_trouvees)} opportunité(s) "
                f"retenue(s) après {statistiques.get('queries_run', len(queries))} requête(s), "
                f"{rejets} écartée(s) sous le seuil de score."
            ),
            "opportunites": opportunites_trouvees,
            "to_review_candidates": resultat.get("to_review_candidates", []),
            "analyzed_sources": resultat.get("analyzed_sources", []),
            "pending_sources": resultat.get("pending_sources", []),
            "continuation_id": resultat.get("continuation_id"),
            "source_groups": resultat.get("source_groups", []),
            "queries": resultat.get("queries", []),
            "analysis_strategy": resultat.get("analysis_strategy"),
            "collection_complete": resultat.get("collection_complete"),
            "collection_diagnostics": resultat.get("collection_diagnostics", {}),
            "navigation_sources": resultat.get("navigation_sources", []),
            "analysis_batches": resultat.get("analysis_batches", []),
            "statistics": statistiques,
        })

    except auto_detection.DetectionAutoEnCours:
        yield _sse("erreur", {"message": "Une détection est déjà en cours. Réessayez dans quelques instants."})
        yield _sse("fin", {"status": "in_progress", "total": 0, "sources": 0, "rejets": 0})
    except Exception as exc:
        logger.exception("❌ Erreur stream détection M1 : %s", exc)
        yield _sse("erreur", {"message": "Erreur interne lors de la détection."})
        yield _sse("fin", {"status": "technical_error", "total": 0, "sources": 0, "rejets": 0})


@sse_router.get(
    "/ia/veille/detecter/stream",
    tags=["M1 - Veille Marché"],
    operation_id="streamDetectionOpportunites",
    summary="Mode 2 — Détection automatique en streaming (Server-Sent Events)",
    description=(
        "Lance la détection automatique et émet les résultats en temps réel "
        "via Server-Sent Events. Événements : debut, requete, analyse, "
        "opportunite, rejet_info, erreur, fin.\n\n"
        "La recherche utilise les fournisseurs configurés. Les erreurs techniques et "
        "les recherches sans opportunité pertinente sont signalées séparément."
    ),
)
async def stream_detection(
    min_score: int = Query(default=40, ge=0, le=100),
    limit: int = Query(default=20, ge=1, le=100),
    sync_backend: bool = Query(default=True),
    token: str | None = Query(default=None, include_in_schema=False),
    principal=Depends(verify_api_key_sse),
):
    return StreamingResponse(
        _stream_detection(min_score=min_score, limit=limit, sync_backend=sync_backend, owner=str(getattr(principal, "id", "internal"))),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


class ReprendreSourcesRequest(BaseModel):
    continuation_id: str = Field(..., min_length=20, max_length=100)


@router.post("/ia/veille/sources/reprendre", tags=["M1 - Veille Marché"])
async def reprendre_sources(payload: ReprendreSourcesRequest, principal=Depends(verify_api_key)):
    if DEMO_MODE:
        raise HTTPException(409, "La reprise des sources est disponible uniquement en mode réel.")
    from app.services.veille.pending_service import resume
    owner = str(getattr(principal, "id", "internal"))
    result = await resume(payload.continuation_id, owner, orchestrator)
    from app.services.veille.result_context_service import remember, latest
    previous = latest(owner)
    if previous:
        by_url = {item.get("url") or item.get("title"): item for item in previous.get("opportunities", []) or []}
        by_url.update({item.get("url") or item.get("title"): item for item in result.get("opportunities", [])})
        merged = {**result, "opportunities": sorted(by_url.values(), key=lambda item: item.get("score", 0), reverse=True)}
        if previous.get("status") == "partial": merged["status"] = "partial"
        remember(owner, merged)
    else:
        remember(owner, result)
    return result


@router.get("/ia/veille/dernier-resultat", tags=["M1 - Veille Marché"])
async def dernier_resultat_veille(principal=Depends(verify_api_key)):
    from app.services.veille.result_context_service import latest
    result = latest(str(getattr(principal, "id", "internal")))
    if not result:
        raise HTTPException(404, "Aucune détection récente accessible pour cette session.")
    return {"success": True, "data": result}
