from uuid import UUID
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Response, Query, status
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