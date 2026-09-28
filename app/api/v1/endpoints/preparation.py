from uuid import UUID
from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.core.dependencies import require_role
from app.models.user import User
from app.schemas.preparation import EDTGeneratorOutput
from app.services.preparation_service import PreparationService


router = APIRouter(
    prefix="/projets",
    tags=["Préparation - IA"]
)

def get_preparation_service(db: Session = Depends(get_db)) -> PreparationService:
    return PreparationService(db)


@router.post(
    "/{projet_id}/edt/ingest-ia}",
    status_code=status.HTTP_201_CREATED,
    summary="Ingestion du contrat IA pour l'EDT"
)
def ingest_ia_edt(
    projet_id: UUID,
    payload: EDTGeneratorOutput,
    service: PreparationService = Depends(get_preparation_service),
    current_user: User = Depends(require_role("SYSTEM", "DIRECTION", "ASSISTANT"))
):
    """ Reçoit le JSON stricte généré par le LLM, le valide via Pydantic"""
    service.ingest_ia_edt_contract(projet_id, payload)
    return {"status": "succes", "message": f"Contrat IA ingéré avec succès pour le projet {projet_id}"}