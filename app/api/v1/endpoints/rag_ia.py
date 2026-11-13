# app/api/v1/endpoints/rag_ia.py
# ============================================================
# ROUTES IA — Module RAG (C3)
# ============================================================
# Étape E : POST /ia/rag/chat, GET /ia/rag/documents/{hash}/fichier,
# GET /ia/rag/formations. Pas de HITL sur le chat (usage interne, mission).
# Étape H : POST /ia/rag/indexer-document (arrière-plan), POST
# /ia/rag/rechercher, GET /ia/rag/statut/{hash}, GET /ia/rag/health.
# ============================================================

import asyncio
import json
import logging
from dataclasses import asdict
from pathlib import Path
from uuid import UUID, uuid4

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Request
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from app.core.dependencies import get_current_tenant_user
from app.database import get_db
from app.models.formation import Session as TrainingSession
from app.models.user import User

from app.orchestrator.chat_orchestrator import get_chat_orchestrator
from app.orchestrator.rag_orchestrator import get_rag_orchestrator
from app.schemas.rag_ia import (
    ChatRequest,
    ChatResponse,
    FormationResume,
    GenererPortfolioRequest,
    GenererQuestionsRequest,
    GenererSyllabusRequest,
    IndexerDocumentRequest,
    RechercherRequest,
)
from app.services.rag import catalogue_service as catalogue
from app.services.rag import registry_service as registre
from app.services.veille.access_service import verify_api_key
from app.services.storage import get_storage
from app.services.storage.storage_service import LocalStorageService
from app.services.rag.trainer_access import assigned_formation_codes, assigned_session_ids, get_accessible_session, is_trainer
from app.core.dependencies import require_role
from app.services.rag import conversation_service as conversations

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/ia/rag",
    tags=["C3 — IA RAG"],
    dependencies=[Depends(verify_api_key), Depends(get_current_tenant_user)],
)

DOSSIER_FICHIERS_ORIGINAUX = Path(__file__).resolve().parents[4] / "data" / "rag" / "fichiers"


def _session_scope(db: Session, user: User, session_id: str | None):
    if is_trainer(user) and not session_id:
        raise HTTPException(status_code=422, detail="Sélectionnez une session qui vous est affectée.")
    return get_accessible_session(db, user, session_id) if session_id else None


def _is_direction(user: User) -> bool:
    role_val = getattr(user, "role", None)
    role_str = role_val.value if hasattr(role_val, "value") else str(role_val or "")
    return role_str == "DIRECTION"


@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest, current_user: User = Depends(get_current_tenant_user), db: Session = Depends(get_db)):
    """Assistant documentaire — route unique pour les 9 types de message
    (voir chat_orchestrator.py). Aucun HITL (usage interne)."""
    session = _session_scope(db, current_user, str(request.session_id) if request.session_id else None)
    logger.info(
        "RAG chat scope: streaming=false session_id=%s module=%s",
        str(session.id) if session else None, request.module,
    )
    formation_code = session.formation_code if session else request.formation_code
    allowed_codes = assigned_formation_codes(db, current_user) if is_trainer(current_user) else None
    allowed_sessions = assigned_session_ids(db, current_user) if is_trainer(current_user) else None
    # Sources visibles uniquement pour la DIRECTION
    hide_refs = not _is_direction(current_user)
    try:
        orchestrateur = get_chat_orchestrator()
        resultat = await orchestrateur.traiter_message(
            request.message, request.conversation_id, formation_code,
            session_id=str(session.id) if session else None, module=request.module,
            allowed_formation_codes=allowed_codes, allowed_session_ids=allowed_sessions,
            hide_references=hide_refs,
            user_id=str(current_user.id),
        )
        return resultat
    except Exception as exc:
        logger.exception(f"❌ Erreur chat RAG : {exc}")
        raise HTTPException(status_code=500, detail=f"Erreur interne du chat : {type(exc).__name__}")


@router.post("/chat/stream", summary="Chat documentaire avec progression en temps réel")
async def chat_stream(payload: ChatRequest, request: Request, current_user: User = Depends(get_current_tenant_user), db: Session = Depends(get_db)):
    session = _session_scope(db, current_user, str(payload.session_id) if payload.session_id else None)
    logger.info(
        "RAG chat scope: streaming=true session_id=%s module=%s",
        str(session.id) if session else None, payload.module,
    )
    formation_code = session.formation_code if session else payload.formation_code
    allowed_codes = assigned_formation_codes(db, current_user) if is_trainer(current_user) else None
    allowed_sessions = assigned_session_ids(db, current_user) if is_trainer(current_user) else None
    # Sources visibles uniquement pour la DIRECTION
    hide_refs = not _is_direction(current_user)
    orchestrateur = get_chat_orchestrator()

    async def produire():
        trace_id = uuid4().hex[:12]
        queue: asyncio.Queue[dict] = asyncio.Queue()
        streaming_active = False  # True once real LLM tokens start arriving

        async def progress(stage: str, label: str):
            # Don't push status events once real tokens are flowing
            if not streaming_active:
                await queue.put({"type": stage, "message": label})

        async def on_token(token: str):
            nonlocal streaming_active
            streaming_active = True
            await queue.put({"type": "token", "text": token})

        async def envoyer(data: dict):
            return "data: " + json.dumps(data, ensure_ascii=False) + "\n\n"

        async def executer():
            return await orchestrateur.traiter_message(
                payload.message, payload.conversation_id, formation_code,
                session_id=str(session.id) if session else None, module=payload.module,
                allowed_formation_codes=allowed_codes, allowed_session_ids=allowed_sessions,
                hide_references=hide_refs,
                user_id=str(current_user.id),
                on_progress=progress,
                on_token=on_token,
            )

        task = asyncio.create_task(executer())
        try:
            while not task.done() or not queue.empty():
                if await request.is_disconnected():
                    task.cancel()
                    return
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=0.2)
                    yield await envoyer(event)
                except TimeoutError:
                    continue

            resultat = await task
            if hide_refs:
                resultat["sources"] = []

            # If streaming was not activated (non-LLM paths: catalogue, conversationnel…),
            # simulate token streaming from the full response text.
            if not streaming_active:
                texte = resultat.get("reponse", "")
                if texte:
                    yield await envoyer({"type": "status", "message": "Réponse prête. Affichage du résultat…"})
                    reste = texte
                    while reste:
                        if await request.is_disconnected():
                            return
                        limite = min(120, len(reste))
                        if limite < len(reste):
                            coupure = reste.rfind(" ", 0, limite)
                            if coupure >= 60:
                                limite = coupure + 1
                        yield await envoyer({"type": "token", "text": reste[:limite]})
                        reste = reste[limite:]
                        await asyncio.sleep(0)

            yield await envoyer({"type": "meta", "data": {k: resultat.get(k) for k in ("conversation_id", "type_reponse", "sources", "formation_resolue", "suggestions", "duree_ms")}})
            yield await envoyer({"type": "done"})
        except asyncio.CancelledError:
            task.cancel()
            raise
        except Exception as exc:
            logger.exception("Erreur chat RAG SSE [%s] : %s", trace_id, exc)
            yield await envoyer({
                "type": "error",
                "message": "La réponse documentaire n’a pas pu être préparée. Réessayez ou transmettez le code au support.",
                "trace_id": trace_id,
            })

    return StreamingResponse(
        produire(), media_type="text/event-stream",
        headers={"Cache-Control": "no-cache, no-transform", "X-Accel-Buffering": "no", "Connection": "keep-alive"},
    )


# ============================================================
# GESTION DES CONVERSATIONS (mémoire — max 20 par utilisateur)
# ============================================================

@router.get("/conversations", summary="Liste des conversations de l'utilisateur (max 20)")
async def lister_conversations_utilisateur(current_user: User = Depends(get_current_tenant_user)):
    """Retourne les conversations du plus récent au plus ancien."""
    user_id = str(current_user.id)
    data = conversations.lister_conversations(user_id)
    return {"success": True, "total": len(data), "data": data}


@router.get("/conversations/{conversation_id}", summary="Détail d'une conversation (échanges)")
async def obtenir_conversation(conversation_id: str, current_user: User = Depends(get_current_tenant_user)):
    """Retourne les échanges d'une conversation pour la reprendre dans l'interface."""
    conv = conversations.charger_conversation(conversation_id)
    if conv.user_id and conv.user_id != str(current_user.id):
        raise HTTPException(status_code=403, detail="Accès refusé à cette conversation.")
    echanges = [{"role": e.role, "texte": e.texte} for e in conv.echanges]
    return {
        "success": True,
        "conversation_id": conversation_id,
        "titre": conv.titre or "Nouvelle conversation",
        "echanges": echanges,
        "derniere_formation_code": conv.derniere_formation_code,
        "cree_le": conv.cree_le,
        "mis_a_jour_le": conv.mis_a_jour_le,
    }


@router.delete("/conversations/{conversation_id}", summary="Supprimer une conversation")
async def supprimer_conversation(conversation_id: str, current_user: User = Depends(get_current_tenant_user)):
    user_id = str(current_user.id)
    supprime = conversations.supprimer_conversation(conversation_id, user_id)
    if not supprime:
        raise HTTPException(status_code=404, detail="Conversation introuvable ou accès refusé.")
    return {"success": True, "message": "Conversation supprimée.", "conversation_id": conversation_id}


class RenommerConversationRequest(BaseModel):
    titre: str


class FeedbackRequest(BaseModel):
    index_echange: int
    feedback: str  # "positif" | "negatif"


@router.patch("/conversations/{conversation_id}/rename", summary="Renommer une conversation")
async def renommer_conversation(conversation_id: str, body: RenommerConversationRequest, current_user: User = Depends(get_current_tenant_user)):
    conv = conversations.charger_conversation(conversation_id)
    if conv.user_id and conv.user_id != str(current_user.id):
        raise HTTPException(status_code=403, detail="Accès refusé à cette conversation.")
    titre = body.titre.strip()[:100]
    if not titre:
        raise HTTPException(status_code=400, detail="Le titre ne peut pas être vide.")
    conv.titre = titre
    conversations.sauvegarder_conversation(conv)
    return {"success": True, "conversation_id": conversation_id, "titre": titre}


@router.post("/conversations/{conversation_id}/feedback", summary="Feedback 👍/👎 sur un échange")
async def noter_message(conversation_id: str, body: FeedbackRequest, current_user: User = Depends(get_current_tenant_user)):
    conv = conversations.charger_conversation(conversation_id)
    if conv.user_id and conv.user_id != str(current_user.id):
        raise HTTPException(status_code=403, detail="Accès refusé à cette conversation.")
    if body.feedback not in ("positif", "negatif"):
        raise HTTPException(status_code=400, detail="feedback doit être 'positif' ou 'negatif'.")
    ok = conversations.noter_echange(conversation_id, body.index_echange, body.feedback)
    if not ok:
        raise HTTPException(status_code=404, detail="Échange introuvable ou n'est pas une réponse assistant.")
    return {"success": True, "conversation_id": conversation_id, "index_echange": body.index_echange, "feedback": body.feedback}


@router.get("/documents/{doc_hash}/fichier")
async def telecharger_document(doc_hash: str, current_user: User = Depends(get_current_tenant_user), db: Session = Depends(get_db)):
    """Télécharge le fichier original d'un document indexé (par son hash).
    Pour un PDF, l'appelant peut ajouter #page=N à l'URL retournée."""
    if not doc_hash.isalnum() or len(doc_hash) != 64:
        raise HTTPException(status_code=400, detail="Hash de document invalide.")

    entree = registre.obtenir_entree(doc_hash)
    if entree is None:
        raise HTTPException(status_code=404, detail="Document introuvable dans le registre.")
    if entree.session_id:
        _session_scope(db, current_user, entree.session_id)
    elif is_trainer(current_user):
        raise HTTPException(status_code=404, detail="Ce support n’est pas classé dans une session accessible.")

    storage = get_storage()
    if not isinstance(storage, LocalStorageService):
        raise HTTPException(status_code=501, detail="Le téléchargement direct de fichiers n’est disponible qu’avec le stockage local.")
    chemin = storage.chemin_local(doc_hash, Path(entree.fichier).suffix.lower())
    if not chemin.is_file():
        raise HTTPException(status_code=404, detail="Fichier original introuvable sur disque.")

    return FileResponse(path=str(chemin), filename=entree.fichier)


@router.get("/formations")
async def lister_formations(db: Session = Depends(get_db), current_user: User = Depends(get_current_tenant_user)):
    """Catalogue RAG + codes des formations déjà utilisées dans les sessions du tenant."""
    formations = catalogue.charger_catalogue()
    par_code = {formation.code: formation for formation in formations}
    sessions = db.query(TrainingSession.formation_code, TrainingSession.titre).filter(
        TrainingSession.formation_code.isnot(None),
        TrainingSession.formation_code != "",
    ).all()
    for code, titre in sessions:
        if code not in par_code:
            par_code[code] = type("FormationSession", (), {"code": code, "titre": titre, "domaine": None})()

    if is_trainer(current_user):
        codes_autorises = assigned_formation_codes(db, current_user)
        par_code = {code: formation for code, formation in par_code.items() if code in codes_autorises}

    resultat = []
    for f in par_code.values():
        nb = sum(
            1 for e in registre.entrees_pour_formation(f.code) if e.statut == "indexe"
        )
        resultat.append(FormationResume(
            code=f.code, titre=f.titre, domaine=f.domaine, nb_supports_indexes=nb,
        ))
    return {"success": True, "total": len(resultat), "data": [r.model_dump() for r in resultat]}


@router.get("/sessions", summary="Sessions accessibles pour classer les supports RAG")
async def lister_sessions_rag(db: Session = Depends(get_db), current_user: User = Depends(get_current_tenant_user)):
    query = db.query(TrainingSession)
    if is_trainer(current_user):
        ids = assigned_session_ids(db, current_user)
        if not ids:
            return {"success": True, "total": 0, "data": []}
        query = query.filter(TrainingSession.id.in_([UUID(value) for value in ids]))
    sessions = query.order_by(TrainingSession.date_debut.desc()).all()
    supports = list(registre.charger_registre().values())
    data = []
    for session in sessions:
        docs = [e for e in supports if e.statut == "indexe" and e.session_id == str(session.id)]
        # Une session comprend plusieurs séances/modules. Les thèmes déjà
        # planifiés sont proposés comme classement, en plus des modules
        # utilisés par les supports déjà indexés.
        seance_modules = [seance.theme for seance in (session.seances or []) if seance.theme]
        data.append({
            "id": str(session.id), "session_id": str(session.id), "titre": session.titre,
            "formation_code": session.formation_code, "date_debut": str(session.date_debut),
            "date_fin": str(session.date_fin), "nb_supports_indexes": len(docs),
            "modules": sorted({*seance_modules, *(e.module for e in docs if e.module)}),
            "seances": [
                {"id": str(seance.id), "date": str(seance.date), "theme": seance.theme}
                for seance in sorted(session.seances or [], key=lambda item: (item.date, item.heure_debut or ""))
            ],
        })
    return {"success": True, "total": len(data), "data": data}


@router.get("/documents/{doc_hash}/extraits", summary="Inspecter les chunks réellement enregistrés")
def extraits_document(doc_hash: str, offset: int = Query(0, ge=0), limit: int = Query(20, ge=1, le=100), collection: str | None = Query(None, max_length=30), current_user: User = Depends(get_current_tenant_user), db: Session = Depends(get_db)):
    if not doc_hash.isalnum() or len(doc_hash) != 64:
        raise HTTPException(400, "Hash de document invalide.")
    entree = registre.obtenir_entree(doc_hash)
    if entree is None:
        raise HTTPException(404, "Document introuvable dans le registre.")
    if entree.session_id:
        _session_scope(db, current_user, entree.session_id)
    elif is_trainer(current_user):
        raise HTTPException(status_code=404, detail="Ce support n’est pas classé dans une session accessible.")
    from app.services.rag.knowledge_repository import KnowledgeRepository
    return {"success": True, **KnowledgeRepository().lister_chunks_document(doc_hash, offset, limit, collection)}


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


@router.post(
    "/questions/exporter-m5",
    summary="[C3→M5] Export questions RAG → format test_avant/test_apres pour FormGeneratorService",
)
async def exporter_questions_m5(request: GenererQuestionsRequest):
    """Génère les questions de révision depuis les supports indexés et les
    structure au format M5 (test_avant / test_apres). Résultat injectable
    directement dans le champ ``supports`` de FormGeneratorService.

    Flux recommandé :
      1. Indexer les supports de la formation via POST /ia/rag/indexer-document
      2. Appeler ce endpoint pour obtenir test_avant + test_apres
      3. Injecter ``supports_resume`` dans ``session_info.supports`` lors
         de la génération des formulaires (POST /ia/formations/generer-formulaires)
    """
    try:
        orchestrateur = get_rag_orchestrator()
        return await orchestrateur.exporter_questions_m5(
            request.formation_code, request.nb_questions_max
        )
    except Exception as e:
        _gerer_erreur(e, "exporter_questions_m5")


@router.post(
    "/portfolio/{review_id}/exporter-m3",
    summary="[C3→M3] Export portfolio APPROUVÉ → références pour offre technique",
)
async def exporter_portfolio_m3(review_id: str):
    """Exporte un portfolio HITL approuvé au format M3 (champ references
    de l'annexe de l'offre technique).

    Flux recommandé :
      1. Générer le portfolio via POST /ia/rag/portfolio
      2. Approuver via POST /ia/rag/reviews/{review_id}/approve
      3. Appeler ce endpoint pour obtenir la liste des références
      4. Injecter ``references`` dans ``session_info.references_portfolio``
         lors de la génération de l'offre (POST /ia/offres/generer)
    """
    try:
        orchestrateur = get_rag_orchestrator()
        return await orchestrateur.exporter_portfolio_m3(review_id)
    except Exception as e:
        _gerer_erreur(e, "exporter_portfolio_m3")


# ============================================================
# ÉTAPE H — Ingestion en arrière-plan, recherche, statut, santé
# ============================================================

@router.post(
    "/indexer-document",
    summary="[C3] Indexer un document (arrière-plan) — réponse immédiate",
)
async def indexer_document(request: IndexerDocumentRequest, background_tasks: BackgroundTasks, current_user: User = Depends(get_current_tenant_user), db: Session = Depends(get_db)):
    """
    Calcule le hash et vérifie l'idempotence SYNCHRONEMENT (rapide), puis
    répond IMMÉDIATEMENT (statut='en_cours' ou 'deja_indexe'). L'appel
    Voyage réel (découpage + embeddings + insertion) est planifié en
    arrière-plan via BackgroundTasks — suivre la progression avec
    GET /ia/rag/statut/{hash}.
    """
    session = _session_scope(db, current_user, str(request.session_id))
    if session and request.formation_code and request.formation_code != session.formation_code:
        raise HTTPException(status_code=422, detail="Le code formation ne correspond pas à la session choisie.")
    request.formation_code = session.formation_code if session else request.formation_code
    if is_trainer(current_user):
        try:
            doc_hash = registre.calculer_hash_fichier(request.chemin_fichier)
        except (OSError, ValueError):
            raise HTTPException(status_code=404, detail="Fichier de support introuvable.")
        entree = registre.obtenir_entree(doc_hash)
        if entree is None or entree.formation_code != request.formation_code or entree.session_id != str(session.id):
            raise HTTPException(status_code=403, detail="Un formateur ne peut indexer que les fichiers déposés pour la session qui lui est affectée.")
    try:
        orchestrateur = get_rag_orchestrator()
        info = orchestrateur.preparer_indexation(
            request.chemin_fichier, request.formation_code, request.collection,
            session_id=str(session.id) if session else str(request.session_id), module=request.module,
        )
        if not info["deja_indexe"]:
            background_tasks.add_task(
                orchestrateur.ingerer_fichier,
                request.chemin_fichier, request.formation_code, request.collection, info["fichier"],
                session_id=str(session.id) if session else str(request.session_id), module=request.module,
            )
        return {
            "success": True, "hash": info["hash"], "fichier": info["fichier"],
            "statut": "deja_indexe" if info["deja_indexe"] else "en_cours",
        }
    except Exception as e:
        _gerer_erreur(e, "indexer_document")


@router.post("/rechercher", summary="[C3] Recherche vectorielle dans les supports indexés")
async def rechercher(request: RechercherRequest, current_user: User = Depends(get_current_tenant_user), db: Session = Depends(get_db)):
    session = _session_scope(db, current_user, str(request.session_id) if request.session_id else None)
    formation_code = session.formation_code if session else request.formation_code
    try:
        from app.services.rag import recherche_service as recherche
        kwargs = {}
        if request.top_k is not None:
            kwargs["top_k"] = request.top_k
        if request.seuil_min is not None:
            kwargs["seuil_min"] = request.seuil_min
        resultats = await recherche.rechercher(
            request.requete, collection=request.collection, formation_code=formation_code,
            session_id=str(session.id) if session else None, module=request.module,
            domaine=request.domaine, annee=request.annee, type_support=request.type_support, **kwargs,
        )
        data = [vars(r) for r in resultats]
        if is_trainer(current_user):
            for result in data:
                result.pop("fichier", None)
                result.pop("page_debut", None)
                result.pop("page_fin", None)
        return {"success": True, "total": len(data), "data": data}
    except Exception as e:
        _gerer_erreur(e, "rechercher")


@router.get("/statut/{doc_hash}", summary="[C3] Statut d'indexation d'un document (par hash)")
async def statut_indexation(doc_hash: str, current_user: User = Depends(get_current_tenant_user), db: Session = Depends(get_db)):
    if not doc_hash.isalnum() or len(doc_hash) != 64:
        raise HTTPException(status_code=400, detail="Hash de document invalide.")

    entree = registre.obtenir_entree(doc_hash)
    if entree is None:
        raise HTTPException(status_code=404, detail="Document introuvable dans le registre.")
    if entree.session_id:
        _session_scope(db, current_user, entree.session_id)
    elif is_trainer(current_user):
        raise HTTPException(status_code=404, detail="Ce support n’est pas classé dans une session accessible.")

    return {"success": True, "data": asdict(entree)}


@router.patch(
    "/documents/{doc_hash}/archiver",
    summary="[C3] Archiver un support (chunks retirés, fichier conservé — restaurable)",
)
async def archiver_document(doc_hash: str, background_tasks: BackgroundTasks, current_user: User = Depends(get_current_tenant_user), db: Session = Depends(get_db)):
    """Retire les chunks de la base vectorielle mais garde le fichier original.
    Le support peut être restauré (ré-indexé) sans re-upload.
    Réservé à DIRECTION et ADMIN."""
    if not doc_hash.isalnum() or len(doc_hash) != 64:
        raise HTTPException(status_code=400, detail="Hash de document invalide.")
    role_val = getattr(current_user, "role", None)
    role_str = role_val.value if hasattr(role_val, "value") else str(role_val or "")
    if role_str not in ("DIRECTION", "ADMIN"):
        raise HTTPException(status_code=403, detail="Seuls DIRECTION et ADMIN peuvent archiver un document.")
    entree = registre.obtenir_entree(doc_hash)
    if entree is None:
        raise HTTPException(status_code=404, detail="Document introuvable dans le registre.")
    if entree.session_id:
        _session_scope(db, current_user, entree.session_id)
    try:
        orchestrateur = get_rag_orchestrator()
        resultat = await orchestrateur.archiver_document(doc_hash)
        return {"success": True, **resultat}
    except Exception as e:
        _gerer_erreur(e, "archiver_document")


@router.patch(
    "/documents/{doc_hash}/restaurer",
    summary="[C3] Restaurer un support archivé (ré-indexation depuis le fichier conservé)",
)
async def restaurer_document(doc_hash: str, background_tasks: BackgroundTasks, current_user: User = Depends(get_current_tenant_user), db: Session = Depends(get_db)):
    """Ré-indexe un document archivé depuis son fichier original conservé.
    Échoue proprement si le fichier a été supprimé (ré-upload nécessaire).
    Réservé à DIRECTION et ADMIN."""
    if not doc_hash.isalnum() or len(doc_hash) != 64:
        raise HTTPException(status_code=400, detail="Hash de document invalide.")
    role_val = getattr(current_user, "role", None)
    role_str = role_val.value if hasattr(role_val, "value") else str(role_val or "")
    if role_str not in ("DIRECTION", "ADMIN"):
        raise HTTPException(status_code=403, detail="Seuls DIRECTION et ADMIN peuvent restaurer un document.")
    entree = registre.obtenir_entree(doc_hash)
    if entree is None:
        raise HTTPException(status_code=404, detail="Document introuvable dans le registre.")
    try:
        orchestrateur = get_rag_orchestrator()
        background_tasks.add_task(orchestrateur.restaurer_document, doc_hash)
        return {"success": True, "hash": doc_hash, "statut": "restauration_en_cours",
                "message": "La ré-indexation est lancée en arrière-plan. Suivre via GET /ia/rag/statut/{hash}."}
    except Exception as e:
        _gerer_erreur(e, "restaurer_document")


@router.get("/stats/cache", summary="Statistiques cache RAG (embeddings + réponses)")
async def stats_cache(current_user: User = Depends(get_current_tenant_user)):
    from app.services.rag import query_cache_service as qcache
    from app.services.rag import response_cache_service as rcache
    return {
        "success": True,
        "cache_embeddings": {"entrees": qcache.taille_cache()},
        "cache_reponses": rcache.stats(),
    }


@router.delete("/stats/cache", summary="Vider le cache des réponses LLM")
async def vider_cache_reponses(current_user: User = Depends(get_current_tenant_user)):
    from app.services.rag import response_cache_service as rcache
    n = rcache.vider_cache()
    return {"success": True, "entrees_supprimees": n}


@router.get("/health", summary="[C3] État du module RAG")
async def health_check():
    try:
        from app.services.rag import get_package_status
        return {"success": True, **get_package_status()}
    except Exception as e:
        _gerer_erreur(e, "health_check")


class ValidationRagRequest(BaseModel):
    reviewer_note: str = Field(..., min_length=2, max_length=1000)


@router.post("/reviews/{review_id}/approve", summary="Approuver un portfolio ou syllabus C3")
async def approuver_contenu_rag(review_id: str, payload: ValidationRagRequest):
    from app.services.hitl import approve_review, get_review
    review = get_review(review_id)
    if not review or review.get("agent_id") not in {"agent_rag_portfolio", "agent_rag_syllabus"}:
        raise HTTPException(404, "Validation RAG introuvable")
    return {"success": True, "review": approve_review(review_id, payload.reviewer_note)}


@router.get("/reviews", summary="Retrouver les brouillons C3 en attente")
async def lister_reviews_rag():
    from app.services.hitl import list_pending
    return {"success": True, "data": list_pending(agent_id="agent_rag_portfolio") + list_pending(agent_id="agent_rag_syllabus")}


@router.get("/reviews/{review_id}", summary="Relire un brouillon C3")
async def lire_review_rag(review_id: str):
    from app.services.hitl import get_review
    review = get_review(review_id)
    if not review or review.get("agent_id") not in {"agent_rag_portfolio", "agent_rag_syllabus"}:
        raise HTTPException(404, "Validation RAG introuvable")
    return {"success": True, "data": review}


@router.delete("/reviews/{review_id}", summary="Supprimer un brouillon C3 encore en attente")
async def supprimer_review_rag(review_id: str, _current_user=Depends(require_role("DIRECTION", "ADMIN", "ASSISTANT"))):
    from app.services.hitl import delete_pending_review, get_review
    review = get_review(review_id)
    if not review or review.get("agent_id") not in {"agent_rag_portfolio", "agent_rag_syllabus"}:
        raise HTTPException(404, "Validation RAG introuvable")
    result = delete_pending_review(review_id)
    if result is False:
        raise HTTPException(409, "Cette validation a déjà été traitée et ne peut plus être supprimée.")
    if result is None:
        raise HTTPException(404, "Validation RAG introuvable")
    return {"success": True, "message": "Validation RAG en attente supprimée.", "review_id": review_id}


@router.post("/reviews/{review_id}/reject", summary="Refuser un brouillon C3")
async def refuser_contenu_rag(review_id: str, payload: ValidationRagRequest):
    from app.services.hitl import get_review, reject_review
    review = get_review(review_id)
    if not review or review.get("agent_id") not in {"agent_rag_portfolio", "agent_rag_syllabus"}:
        raise HTTPException(404, "Validation RAG introuvable")
    return {"success": True, "review": reject_review(review_id, payload.reviewer_note)}


@router.get("/exports/{filename}", summary="Télécharger un export DOCX C3")
async def telecharger_export_rag(filename: str):
    if Path(filename).name != filename or "\\" in filename or not filename.endswith(".docx") or not filename.startswith(("portfolio_", "syllabus_")):
        raise HTTPException(400, "Nom d'export invalide")
    from app.services.rag.rag_document_generator import get_tenant_exports_dir
    path = get_tenant_exports_dir() / filename
    if not path.is_file():
        raise HTTPException(404, "Export introuvable")
    return FileResponse(path, filename=filename)


class IndexerGuidesRequest(BaseModel):
    noms: list[str] = Field(default_factory=lambda: ["00_parcours_interface_actuel.md"], min_length=1, max_length=12)


@router.get("/guides", summary="Lister les guides de fonctionnement disponibles")
async def lister_guides():
    directory = Path(__file__).resolve().parents[4] / "docs" / "guides_plateforme"
    return {"success": True, "data": [{"nom": path.name} for path in sorted(directory.glob("*.md"))]}


@router.post("/guides/indexer", summary="Indexer les guides sélectionnés dans l'aide plateforme")
async def indexer_guides(payload: IndexerGuidesRequest, background_tasks: BackgroundTasks):
    directory = Path(__file__).resolve().parents[4] / "docs" / "guides_plateforme"
    allowed = {path.name: path for path in directory.glob("*.md")}
    if any(name not in allowed for name in payload.noms):
        raise HTTPException(400, "Guide inconnu")
    orchestrator = get_rag_orchestrator()
    result = []
    for name in dict.fromkeys(payload.noms):
        path = allowed[name]
        info = orchestrator.preparer_indexation(str(path), None, "aide_plateforme")
        if not info["deja_indexe"]:
            background_tasks.add_task(orchestrator.ingerer_fichier, str(path), None, "aide_plateforme", info["fichier"])
        result.append({"fichier": name, "hash": info["hash"], "statut": "deja_indexe" if info["deja_indexe"] else "en_cours"})
    return {"success": True, "data": result}
