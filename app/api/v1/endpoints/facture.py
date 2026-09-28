from uuid import UUID
from typing import List
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.core.dependencies import get_current_user, require_role
from app.models.user import User
from app.schemas.facture import (
    FactureCreate, FactureUpdate, FactureResponse,
    PaiementCreate, PaiementResponse,
    RelanceResponse, RelanceIACreate, RelanceIAResponse,
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


@router.patch(
    "/{facture_id}",
    response_model=FactureResponse,
    summary="Mettre à jour une facture (PATCH partiel)",
    description=(
        "Modifie un ou plusieurs champs d'une facture existante.\n\n"
        "**Tous les champs sont optionnels** (PATCH semantics).\n\n"
        "**Champs modifiables :**\n"
        "- `client` : nom du client\n"
        "- `date_echeance` : nouvelle date d'échéance (`YYYY-MM-DD`)\n"
        "- `statut` : `EMISE` | `PARTIELLEMENT_PAYEE` | `PAYEE` | `EN_RETARD`\n\n"
        "⚠️ Modifier le statut manuellement n'est prévu que pour des corrections "
        "exceptionnelles (ex. passage à `EN_RETARD` ou `ANNULEE`). "
        "Les paiements normaux passent par `POST /factures/{id}/paiments`.\n\n"
        "Retourne **404** si la facture n'existe pas.\n\n"
        "**Rôles autorisés :** DIRECTION, COMPTABLE."
    ),
)
def mettre_a_jour_facture(
    facture_id: UUID,
    data: FactureUpdate,
    service: FactureService = Depends(get_facture_service),
    current_user: User = Depends(require_role("DIRECTION", "COMPTABLE")),
):
    return service.mettre_a_jour_facture(facture_id, data)


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


@router.post(
    "/{facture_id}/relances",
    response_model=RelanceIAResponse,
    status_code=201,
    summary="Enregistrer une relance IA approuvée (HITL)",
)
def enregistrer_relance_ia(
    facture_id: UUID,
    data: RelanceIACreate,
    service: FactureService = Depends(get_facture_service),
    current_user: User = Depends(require_role("DIRECTION", "COMPTABLE")),
):
    """Persiste une relance rédigée par l'IA M7 et approuvée via HITL."""
    return service.enregistrer_relance_ia(facture_id, data)


@router.get(
    "/{facture_id}/relances",
    response_model=List[RelanceIAResponse],
    summary="Lister les relances IA d'une facture",
)
def lister_relances(
    facture_id: UUID,
    service: FactureService = Depends(get_facture_service),
    current_user: User = Depends(get_current_user),
):
    return service.lister_relances(facture_id)