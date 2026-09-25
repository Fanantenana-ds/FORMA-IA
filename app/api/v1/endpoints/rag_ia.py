# app/api/v1/endpoints/rag_ia.py
# ============================================================
# ROUTES IA — Module RAG (C3)
# ============================================================
# Étape E : POST /ia/rag/chat, GET /ia/rag/documents/{hash}/fichier,
# GET /ia/rag/formations. Pas de HITL sur le chat (usage interne, mission).
# Étape H : POST /ia/rag/indexer-document (arrière-plan), POST
# /ia/rag/rechercher, GET /ia/rag/statut/{hash}, GET /ia/rag/health.
# ============================================================

import logging
from dataclasses import asdict
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, HTTPException
from fastapi.responses import FileResponse

from app.orchestrator.chat_orchestrator import get_chat_orchestrator
from app.orchestrator.rag_orchestrator import get_rag_orchestrator
from app.schemas.rag_ia import (
    ChatRequest, ChatResponse, FormationResume,
    GenererPortfolioRequest, GenererSyllabusRequest, GenererQuestionsRequest,
    IndexerDocumentRequest, RechercherRequest,
)
from app.services.rag import catalogue_service as catalogue
from app.services.rag import registry_service as registre

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ia/rag", tags=["C3 — IA RAG"])

DOSSIER_FICHIERS_ORIGINAUX = Path(__file__).resolve().parents[3] / "data" / "rag" / "fichiers"


@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """Assistant documentaire — route unique pour les 9 types de message
    (voir chat_orchestrator.py). Aucun HITL (usage interne)."""
    try:
        orchestrateur = get_chat_orchestrator()
        resultat = await orchestrateur.traiter_message(
            request.message, request.conversation_id, request.formation_code,
        )
        return resultat
    except Exception as exc:
        logger.exception(f"❌ Erreur chat RAG : {exc}")
        raise HTTPException(status_code=500, detail=f"Erreur interne du chat : {type(exc).__name__}")


@router.get("/documents/{doc_hash}/fichier")
async def telecharger_document(doc_hash: str):
    """Télécharge le fichier original d'un document indexé (par son hash).
    Pour un PDF, l'appelant peut ajouter #page=N à l'URL retournée."""
    if not doc_hash.isalnum() or len(doc_hash) != 64:
        raise HTTPException(status_code=400, detail="Hash de document invalide.")

    entree = registre.obtenir_entree(doc_hash)
    if entree is None:
        raise HTTPException(status_code=404, detail="Document introuvable dans le registre.")

    candidats = list(DOSSIER_FICHIERS_ORIGINAUX.glob(f"{doc_hash}.*"))
    if not candidats:
        raise HTTPException(status_code=404, detail="Fichier original introuvable sur disque.")

    return FileResponse(path=str(candidats[0]), filename=entree.fichier)


@router.get("/formations")
async def lister_formations():
    """Formations du catalogue avec leur nombre de supports indexés."""
    formations = catalogue.charger_catalogue()
    resultat = []
    for f in formations:
        nb = sum(
            1 for e in registre.entrees_pour_formation(f.code) if e.statut == "indexe"
        )
        resultat.append(FormationResume(
            code=f.code, titre=f.titre, domaine=f.domaine, nb_supports_indexes=nb,
        ))
    return {"success": True, "total": len(resultat), "data": [r.model_dump() for r in resultat]}


# ============================================================
# ÉTAPE G — Portfolio, syllabus, questions
# ============================================================

def _gerer_erreur(e: Exception, contexte: str):
    if isinstance(e, ValueError):
        detail = str(e)
        code = 404 if "introuvable" in detail.lower() else 422
        raise HTTPException(status_code=code, detail=detail)
    logger.exception(f"❌ Erreur RAG ({contexte}) : {e}")
    raise HTTPException(status_code=500, detail=f"Erreur interne : {type(e).__name__}")


@router.post("/portfolio", summary="[C3] Générer le portfolio (totaux Python + RAG) + HITL")
async def generer_portfolio(request: GenererPortfolioRequest):
    try:
        orchestrateur = get_rag_orchestrator()
        resultat = await orchestrateur.generer_portfolio(request.domaine, request.reference_ao)
        return resultat
    except Exception as e:
        _gerer_erreur(e, "generer_portfolio")


@router.post("/portfolio/{review_id}/exporter", summary="[C3] Export DOCX du portfolio APPROUVÉ")
async def exporter_portfolio(review_id: str):
    try:
        orchestrateur = get_rag_orchestrator()
        return await orchestrateur.exporter_portfolio(review_id)
    except Exception as e:
        _gerer_erreur(e, "exporter_portfolio")


@router.post("/syllabus", summary="[C3] Générer le syllabus (durées vérifiées en Python + RAG) + HITL")
async def generer_syllabus(request: GenererSyllabusRequest):
    try:
        orchestrateur = get_rag_orchestrator()
        modules = [m.model_dump() for m in request.modules]
        resultat = await orchestrateur.generer_syllabus(request.formation_code, modules, request.options)
        return resultat
    except Exception as e:
        _gerer_erreur(e, "generer_syllabus")


@router.post("/syllabus/{review_id}/exporter", summary="[C3] Export DOCX du syllabus APPROUVÉ")
async def exporter_syllabus(review_id: str):
    try:
        orchestrateur = get_rag_orchestrator()
        return await orchestrateur.exporter_syllabus(review_id)
    except Exception as e:
        _gerer_erreur(e, "exporter_syllabus")


@router.post("/generer-questions", summary="[C3] Générer des questions de révision (usage interne, pas de HITL)")
async def generer_questions(request: GenererQuestionsRequest):
    try:
        orchestrateur = get_rag_orchestrator()
        return await orchestrateur.generer_questions(request.formation_code, request.nb_questions_max)
    except Exception as e:
        _gerer_erreur(e, "generer_questions")


# ============================================================
# ÉTAPE H — Ingestion en arrière-plan, recherche, statut, santé
# ============================================================

@router.post(
    "/indexer-document",
    summary="[C3] Indexer un document (arrière-plan) — réponse immédiate",
)
async def indexer_document(request: IndexerDocumentRequest, background_tasks: BackgroundTasks):
    """
    Calcule le hash et vérifie l'idempotence SYNCHRONEMENT (rapide), puis
    répond IMMÉDIATEMENT (statut='en_cours' ou 'deja_indexe'). L'appel
    Voyage réel (découpage + embeddings + insertion) est planifié en
    arrière-plan via BackgroundTasks — suivre la progression avec
    GET /ia/rag/statut/{hash}.
    """
    try:
        orchestrateur = get_rag_orchestrator()
        info = orchestrateur.preparer_indexation(
            request.chemin_fichier, request.formation_code, request.collection,
        )
        if not info["deja_indexe"]:
            background_tasks.add_task(
                orchestrateur.ingerer_fichier,
                request.chemin_fichier, request.formation_code, request.collection, info["fichier"],
            )
        return {
            "success": True, "hash": info["hash"], "fichier": info["fichier"],
            "statut": "deja_indexe" if info["deja_indexe"] else "en_cours",
        }
    except Exception as e:
        _gerer_erreur(e, "indexer_document")


@router.post("/rechercher", summary="[C3] Recherche vectorielle dans les supports indexés")
async def rechercher(request: RechercherRequest):
    try:
        from app.services.rag import recherche_service as recherche
        kwargs = {}
        if request.top_k is not None:
            kwargs["top_k"] = request.top_k
        if request.seuil_min is not None:
            kwargs["seuil_min"] = request.seuil_min
        resultats = await recherche.rechercher(
            request.requete, collection=request.collection, formation_code=request.formation_code,
            domaine=request.domaine, annee=request.annee, type_support=request.type_support, **kwargs,
        )
        return {"success": True, "total": len(resultats), "data": [vars(r) for r in resultats]}
    except Exception as e:
        _gerer_erreur(e, "rechercher")


@router.get("/statut/{doc_hash}", summary="[C3] Statut d'indexation d'un document (par hash)")
async def statut_indexation(doc_hash: str):
    if not doc_hash.isalnum() or len(doc_hash) != 64:
        raise HTTPException(status_code=400, detail="Hash de document invalide.")

    entree = registre.obtenir_entree(doc_hash)
    if entree is None:
        raise HTTPException(status_code=404, detail="Document introuvable dans le registre.")

    return {"success": True, "data": asdict(entree)}


@router.get("/health", summary="[C3] État du module RAG")
async def health_check():
    try:
        from app.services.rag import get_package_status
        return {"success": True, **get_package_status()}
    except Exception as e:
        _gerer_erreur(e, "health_check")
