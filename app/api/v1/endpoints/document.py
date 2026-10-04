# app/api/v1/endpoints/document.py
# ============================================================
# ROUTES BACKEND — Documents (TDR, Offres, Attestations, Supports RAG)
# ============================================================
# Blocs historiques : TDR (POST /tdr), Offres (POST /offre),
#   Attestations (POST /attestations/{session_id}), Export, Validation.
# Bloc J (2026-09-28) : upload multipart supports RAG, liste, suppression.
#   Flow : Frontend → POST /upload → sauvegarde dans data/rag/fichiers/
#   → retourne chemin_fichier → Frontend appelle POST /ia/rag/indexer-document.
# ============================================================

import hashlib
import logging
from pathlib import Path
from typing import List, Optional
from uuid import UUID
from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Response, UploadFile
from sqlalchemy.orm import Session

from app.database import get_db
from app.core.dependencies import get_current_user, require_role
from app.models.user import User
from app.models.document import Document, FormatExport, TypeDocument
from app.schemas.document import (
    TDRRequest,
    DocumentResponse,
    ValidationRequest,
    OffreRequest,
)
from app.services.document_service import DocumentService
from app.services.document_export_service import DocumentExportService
from app.services.rag import registry_service as registre
from app.services.rag.registry_service import initialiser_entree

logger = logging.getLogger(__name__)

# Dossier où sont stockés les fichiers originaux (même chemin que rag_ia.py)
DOSSIER_FICHIERS_RAG = Path(__file__).resolve().parents[4] / "data" / "rag" / "fichiers"

# Extensions acceptées (cohérent avec FORMATS_INDEXABLES du RAG)
EXTENSIONS_AUTORISEES = {".pdf", ".docx", ".pptx", ".xlsx", ".txt", ".md"}
TAILLE_MAX_OCTETS = 50 * 1024 * 1024  # 50 Mo

router = APIRouter(prefix="/documents", tags=["Documents"])


# ─────────────────────────────────────────────────────────────
# Dépendances
# ─────────────────────────────────────────────────────────────
def get_document_service(db: Session = Depends(get_db)) -> DocumentService:
    return DocumentService(db)


def get_document_export_service() -> DocumentExportService:
    return DocumentExportService()

# ─────────────────────────────────────────────────────────────
# CRÉATION — TDR (M2)
# ─────────────────────────────────────────────────────────────
@router.post("/tdr", response_model=DocumentResponse, status_code=201)
def generer_tdr(
    data: TDRRequest,
    service: DocumentService = Depends(get_document_service),
    current_user: User = Depends(require_role("DIRECTION", "ASSISTANT")),
):
    return service.generer_tdr(data)


# ─────────────────────────────────────────────────────────────
# CRÉATION — OFFRE (M3)
# ─────────────────────────────────────────────────────────────
@router.post("/offre", response_model=DocumentResponse, status_code=201)
def generer_offre(
    data: OffreRequest,
    service: DocumentService = Depends(get_document_service),
    current_user: User = Depends(require_role("DIRECTION", "ASSISTANT")),
):
    return service.generer_offre(data)


# ─────────────────────────────────────────────────────────────
# CRÉATION — ATTESTATIONS (M6)
# ─────────────────────────────────────────────────────────────
@router.post(
    "/attestations/{session_id}",
    response_model=List[DocumentResponse],
    status_code=201,
)
def generer_attestations(
    session_id: UUID,
    service: DocumentService = Depends(get_document_service),
    current_user: User = Depends(require_role("DIRECTION", "FORMATEUR")),
):
    return service.generer_attestations(session_id)


# ─────────────────────────────────────────────────────────────
# ✅ NOUVEAU — LISTER tous les documents (avec filtres)
# ─────────────────────────────────────────────────────────────
@router.get("", response_model=List[DocumentResponse])
def lister_documents(
    type: Optional[TypeDocument] = Query(
        None, description="Filtrer par type : TDR, OFFRE, ATTESTATION"
    ),
    statut_validation: Optional[str] = Query(
        None, description="Filtrer par statut : EN_ATTENTE, VALIDE, REJETE"
    ),
    skip: int = Query(0, ge=0, description="Pagination — offset"),
    limit: int = Query(50, ge=1, le=200, description="Pagination — limite"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Liste tous les documents, avec filtres optionnels par type
    et par statut de validation.
    """
    query = db.query(Document)

    if type:
        query = query.filter(Document.type == type)
    if statut_validation:
        query = query.filter(Document.statut_validation == statut_validation)

    return (
        query.order_by(Document.date_generation.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )


# ─────────────────────────────────────────────────────────────
# LECTURE — Un document
# ─────────────────────────────────────────────────────────────
@router.get("/{document_id}", response_model=DocumentResponse)
def get_document(
    document_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    document = db.query(Document).filter(Document.id == document_id).first()
    if not document:
        raise HTTPException(status_code=404, detail="Document introuvable")
    return document


# ─────────────────────────────────────────────────────────────
# VALIDATION HITL
# ─────────────────────────────────────────────────────────────
@router.post("/{document_id}/valider", response_model=DocumentResponse)
def valider_document(
    document_id: UUID,
    data: ValidationRequest,
    service: DocumentService = Depends(get_document_service),
    current_user: User = Depends(require_role("DIRECTION")),
):
    return service.valider(document_id, current_user.id, data.approuve)


# ─────────────────────────────────────────────────────────────
# EXPORT Word / PDF
# ─────────────────────────────────────────────────────────────
@router.get("/{document_id}/export")
def exporter_document(
    document_id: UUID,
    format: FormatExport,
    db: Session = Depends(get_db),
    export_service: DocumentExportService = Depends(get_document_export_service),
    current_user: User = Depends(get_current_user),
):
    document = db.query(Document).filter(Document.id == document_id).first()
    if not document:
        raise HTTPException(status_code=404, detail="Document introuvable")

    contenu, nom_fichier, media_type = export_service.exporter(document, format)

    document.format_export = format
    db.commit()

    return Response(
        content=contenu,
        media_type=media_type,
        headers={"Content-Disposition": f"attachment; filename={nom_fichier}"},
    )


# ─────────────────────────────────────────────────────────────
# ✅ NOUVEAU — SUPPRESSION (admin uniquement)
# ─────────────────────────────────────────────────────────────
@router.delete("/{document_id}", status_code=204)
def supprimer_document(
    document_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("DIRECTION")),
):
    return service.generer_offre(data)


# ============================================================
# BLOC J — Supports RAG : upload, liste, suppression
# ============================================================

def _calculer_hash(contenu: bytes) -> str:
    """SHA-256 du contenu binaire du fichier."""
    return hashlib.sha256(contenu).hexdigest()


@router.post(
    "/upload",
    status_code=201,
    summary="Uploader un support RAG (PDF, DOCX, PPTX, XLSX…)",
    description=(
        "Sauvegarde le fichier dans `data/rag/fichiers/` et l'enregistre dans le registre "
        "d'indexation avec le statut `en_attente`. Le champ `chemin_fichier` retourné permet "
        "d'appeler ensuite `POST /ia/rag/indexer-document` pour lancer l'indexation vectorielle. "
        "Idempotent : si le même fichier (même SHA-256) a déjà été uploadé, le chemin existant "
        "est retourné sans réécriture. Rôles autorisés : DIRECTION, ASSISTANT, FORMATEUR."
    ),
)
async def uploader_support(
    fichier: UploadFile = File(..., description="Fichier à indexer (PDF, DOCX, PPTX, XLSX, TXT, MD)"),
    formation_code: Optional[str] = Form(default=None, description="Code de la formation associée (catalogue RAG)"),
    collection: str = Form(default="support", description="Collection RAG : support | aide_plateforme"),
    current_user: User = Depends(require_role("DIRECTION", "ASSISTANT", "FORMATEUR")),
):
    # Vérification extension
    nom = fichier.filename or "fichier_inconnu"
    ext = Path(nom).suffix.lower()
    if ext not in EXTENSIONS_AUTORISEES:
        raise HTTPException(
            status_code=422,
            detail=f"Extension '{ext}' non supportée. Formats acceptés : {', '.join(sorted(EXTENSIONS_AUTORISEES))}",
        )

    # Lecture et vérification taille
    contenu = await fichier.read()
    if len(contenu) > TAILLE_MAX_OCTETS:
        raise HTTPException(status_code=413, detail=f"Fichier trop volumineux (max {TAILLE_MAX_OCTETS // (1024*1024)} Mo).")
    if len(contenu) == 0:
        raise HTTPException(status_code=422, detail="Le fichier est vide.")

    doc_hash = _calculer_hash(contenu)
    chemin_destination = DOSSIER_FICHIERS_RAG / f"{doc_hash}{ext}"

    # Idempotence : fichier déjà présent
    deja_present = chemin_destination.exists()
    if not deja_present:
        DOSSIER_FICHIERS_RAG.mkdir(parents=True, exist_ok=True)
        chemin_destination.write_bytes(contenu)
        logger.info(f"Support RAG sauvegardé : {chemin_destination}")

    # Enregistrement dans le registre (crée ou retourne l'entrée existante)
    entree = initialiser_entree(
        hash_fichier=doc_hash,
        fichier=nom,
        formation_code=formation_code,
        collection=collection,
    )

    return {
        "success": True,
        "hash": doc_hash,
        "fichier": nom,
        "chemin_fichier": str(chemin_destination),
        "formation_code": formation_code,
        "collection": collection,
        "statut": entree.statut,
        "deja_present": deja_present,
        "taille_octets": len(contenu),
    }


@router.get(
    "/rag/supports",
    summary="Lister les supports RAG uploadés (avec statut d'indexation)",
    description=(
        "Retourne tous les documents présents dans le registre d'indexation RAG. "
        "Filtre optionnel par `formation_code` ou `statut` (en_attente, en_cours, indexe, erreur). "
        "Rôles autorisés : tous les utilisateurs authentifiés."
    ),
)
def lister_supports(
    formation_code: Optional[str] = Query(default=None, description="Filtrer par code de formation"),
    statut: Optional[str] = Query(default=None, description="en_attente | en_cours | indexe | erreur"),
    current_user: User = Depends(get_current_user),
):
    registre_complet = registre.charger_registre()
    entrees = list(registre_complet.values())

    if formation_code:
        entrees = [e for e in entrees if e.formation_code == formation_code]
    if statut:
        entrees = [e for e in entrees if e.statut == statut]

    data = []
    for e in entrees:
        chemin = DOSSIER_FICHIERS_RAG / f"{e.hash}{Path(e.fichier).suffix.lower()}"
        data.append({
            "hash": e.hash,
            "fichier": e.fichier,
            "formation_code": e.formation_code,
            "collection": e.collection,
            "statut": e.statut,
            "nb_chunks": e.nb_chunks,
            "date_debut": e.date_debut,
            "date_fin": e.date_fin,
            "message": e.message,
            "fichier_disponible": chemin.exists(),
            "chemin_fichier": str(chemin),
        })

    return {"success": True, "total": len(data), "data": data}


@router.delete(
    "/rag/supports/{doc_hash}",
    status_code=200,
    summary="Supprimer un support RAG (registre + disque + vecteurs)",
    description=(
        "Supprime complètement un support RAG : retire l'entrée du registre d'indexation, "
        "supprime le fichier physique de `data/rag/fichiers/` et efface tous les chunks "
        "vectorisés de la table `knowledge_base` (pgvector). "
        "Irréversible. Rôles autorisés : DIRECTION, ASSISTANT."
    ),
)
def supprimer_support(
    doc_hash: str,
    current_user: User = Depends(require_role("DIRECTION", "ASSISTANT")),
):
    # Validation format hash (64 hex)
    if not doc_hash.isalnum() or len(doc_hash) != 64:
        raise HTTPException(status_code=422, detail="Hash invalide (SHA-256 attendu, 64 caractères hexadécimaux).")

    entree = registre.obtenir_entree(doc_hash)
    if entree is None:
        raise HTTPException(status_code=404, detail="Support RAG introuvable dans le registre.")

    nb_chunks_supprimes = 0
    fichier_supprime = False

    # 1. Suppression des vecteurs en base
    try:
        from app.services.rag.knowledge_repository import KnowledgeRepository
        repo = KnowledgeRepository()
        nb_chunks_supprimes = repo.supprimer_par_hash(doc_hash)
        logger.info(f"RAG suppression : {nb_chunks_supprimes} chunks supprimés pour hash={doc_hash}")
    except Exception as exc:
        logger.warning(f"Impossible de supprimer les chunks knowledge_base : {exc}")

    # 2. Suppression du fichier physique
    ext = Path(entree.fichier).suffix.lower()
    chemin = DOSSIER_FICHIERS_RAG / f"{doc_hash}{ext}"
    if chemin.exists():
        chemin.unlink()
        fichier_supprime = True
        logger.info(f"RAG suppression : fichier supprimé {chemin}")

    # 3. Suppression du registre
    registre.supprimer_entree(doc_hash)

    return {
        "success": True,
        "hash": doc_hash,
        "fichier": entree.fichier,
        "nb_chunks_supprimes": nb_chunks_supprimes,
        "fichier_supprime": fichier_supprime,
        "message": f"Support '{entree.fichier}' supprimé avec succès.",
    }

    """
    Supprime un document. Réservé à la Direction.
    Refuse la suppression d'un document déjà validé.
    """
    document = db.query(Document).filter(Document.id == document_id).first()
    if not document:
        raise HTTPException(status_code=404, detail="Document introuvable")

    # Sécurité : on ne supprime pas un document validé
    if document.statut_validation and document.statut_validation.value == "VALIDE":
        raise HTTPException(
            status_code=400,
            detail="Impossible de supprimer un document validé",
        )

    db.delete(document)
    db.commit()
    return None
