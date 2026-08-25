from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.core.dependencies import get_current_user, require_role, get_opportunite_analyse_service
from app.models.user import User

from app.database import get_db
from app.repositories.opportunite_repository import OpportuniteRepository
from app.schemas.opportunite import (
    OpportuniteCreate,
    OpportuniteUpdate,
    OpportuniteResponse,
    OpportuniteList,
    OpportuniteAnalyseResult,
    OpportuniteAnalyseRequest
)
from app.services.opportunite_service import OpportuniteService
from app.services.opportunite_analyse_service import OpportuniteAnalyseService

#Route opportunité
router = APIRouter(
    prefix="/opportunites",
    tags=["Opportunités"]
)

def get_opportunite_service(db: Session = Depends(get_db)) -> OpportuniteService:
    repository = OpportuniteRepository(db)

    return OpportuniteService(repository)

@router.post(
    "",
    response_model=OpportuniteResponse,
    status_code=status.HTTP_201_CREATED
)
def create_opportunite(
    data: OpportuniteCreate,
    service: OpportuniteService = Depends(get_opportunite_service),
    current_user: User = Depends(
        require_role("DIRECTION", "ASSISTANT")
    )
):
    return service.create(data)

@router.get(
    "",
    response_model=OpportuniteList
)
def get_opportunites(service: OpportuniteService = Depends(get_opportunite_service), current_user: User = Depends(get_current_user)):
    opportunites = service.get_all()

    return {
        "opportunites": opportunites,
        "total": len(opportunites)
    }

# Route analyse opportunité
@router.post(
    "/analyse",
    response_model=OpportuniteAnalyseResult
)
def analyse_opportunite(
    data: OpportuniteAnalyseRequest,
    analyse_service: OpportuniteAnalyseService = Depends(get_opportunite_analyse_service),
    current_user: User = Depends(get_current_user)
):
    contenu = data.contenu
    if not contenu and data.url:
        contenu = str(data.url)

    return analyse_service.analyse(contenu)

@router.get(
    "/{opportunite_id}",
    response_model=OpportuniteResponse
)
def get_opportunite(opportunite_id: UUID, service: OpportuniteService = Depends(get_opportunite_service), current_user: User = Depends(get_current_user)):
    opportunite = service.get_by_id(opportunite_id)

    if not opportunite:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Opportunité introuvable"
        )

    return opportunite

@router.delete(
    "/{opportunite_id}",
    status_code=status.HTTP_204_NO_CONTENT
)
def delete_opportunite(
    opportunite_id: UUID,
    service: OpportuniteService = Depends(get_opportunite_service),
    current_user: User = Depends(
        require_role("DIRECTION", "ASSISTANT")
    )
):
    deleted = service.delete(opportunite_id)

    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Opportunité introuvable"
        )

    return None

@router.put(
    "/{opportunite_id}",
    response_model=OpportuniteResponse
)
def update_opportunite(
    opportunite_id: UUID, data: OpportuniteUpdate, 
    service: OpportuniteService = Depends(get_opportunite_service),
    current_user: User = Depends(
        require_role("DIRECTION", "ASSISTANT")
    )
):
    updated_opportunite = service.update(opportunite_id, data)

    if not updated_opportunite:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Opportunité introuvable"
        )

    return updated_opportunite
