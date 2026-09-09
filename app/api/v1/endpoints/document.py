from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.core.dependencies import get_current_user, require_role
from app.models.user import User
from app.models.document import Document, FormatExport
from app.schemas.document import TDRRequest, DocumentResponse, ValidationRequest, OffreRequest
from app.services.document_service import DocumentService
from app.services.document_export_service import DocumentExportService

from typing import List

router = APIRouter(
    prefix="/documents",
    tags=["Documents"]
)

def get_document_service(db: Session = Depends(get_db)) -> DocumentService:
    return DocumentService(db)


@router.post("/tdr", response_model=DocumentResponse, status_code=201)
def generer_tdr(
    data: TDRRequest,
    service: DocumentService = Depends(get_document_service),
    current_user: User = Depends(require_role("DIRECTION", "ASSISTANT"))
):
    return service.generer_tdr(data)


@router.post("/{document_id}/valider", response_model=DocumentResponse)
def valider_document(
    document_id: UUID,
    data: ValidationRequest,
    service: DocumentService = Depends(get_document_service),
    current_user: User = Depends(require_role("DIRECTION"))
):
    return service.valider(document_id, current_user.id, data.approuve)


@router.get("/{document_id}", response_model=DocumentResponse)
def get_document(
    document_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    document = db.query(Document).filter(Document.id == document_id).first()
    if not document:
        raise HTTPException(status_code=404, detail="Document introuvable")
    return document

@router.post("/attestations/{session_id}", response_model=List[DocumentResponse], status_code=201)
def generer_attestations(
    session_id: UUID,
    service: DocumentService = Depends(get_document_service),
    current_user: User = Depends(require_role("DIRECTION", "FORMATEUR"))
):
    return service.generer_attestations(session_id)


def get_document_export_service() -> DocumentExportService:
    return DocumentExportService()


@router.get("/{document_id}/export")
def exporter_document(
    document_id: UUID,
    format: FormatExport,
    db: Session = Depends(get_db),
    export_service: DocumentExportService = Depends(get_document_export_service),
    current_user: User = Depends(get_current_user)
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
        headers={"Content-Disposition": f"attachment; filename={nom_fichier}"}
    )


@router.post("/offre", response_model=DocumentResponse, status_code=201)
def generer_offre(
    data: OffreRequest,
    service: DocumentService = Depends(get_document_service),
    current_user: User = Depends(require_role("DIRECTION", "ASSISTANT"))
):
    return service.generer_offre(data)