from uuid import UUID
from typing import List
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.core.dependencies import get_current_user, require_role
from app.models.user import User
from app.schemas.facture import (
    FactureCreate, FactureResponse, PaiementCreate, PaiementResponse, RelanceResponse
)
from app.services.facture_service import FactureService

router = APIRouter(prefix="/factures", tags=["Facturation"])


def get_facture_service(db: Session = Depends(get_db)) -> FactureService:
    return FactureService(db)


@router.post("", response_model=FactureResponse, status_code=201)
def emettre_facture(
    data: FactureCreate,
    service: FactureService = Depends(get_facture_service),
    current_user: User = Depends(require_role("DIRECTION", "COMPTABLE"))
):
    return service.emettre_facture(data)


@router.get("", response_model=List[FactureResponse])
def lister_factures(
    service: FactureService = Depends(get_facture_service),
    current_user: User = Depends(get_current_user)
):
    return service.lister()


@router.get("/{facture_id}", response_model=FactureResponse)
def get_facture(
    facture_id: UUID,
    service: FactureService = Depends(get_facture_service),
    current_user: User = Depends(get_current_user)
):
    return service.get_facture(facture_id)


@router.post("/{facture_id}/paiments", response_model=FactureResponse, status_code=201)
def ajouter_paiement(
    facture_id: UUID,
    data: PaiementCreate,
    service: FactureService = Depends(get_facture_service),
    current_user: User = Depends(require_role("DIRECTION", "COMPTABLE"))
):
    return service.ajouter_paiement(facture_id, data)


@router.post("/{facture_id}/relance", response_model=RelanceResponse)
def generer_relance(
    facture_id: UUID,
    service: FactureService = Depends(get_facture_service),
    current_user: User = Depends(require_role("DIRECTION", "COMPTABLE"))
):
    texte = service.generer_relance(facture_id)
    return RelanceResponse(texte=texte)