# app/api/v1/endpoints/opportunite.py
# ============================================================
# ROUTES BACKEND — Opportunités commerciales
# ============================================================
#
#   POST /opportunites              Créer une opportunité (DIRECTION, ASSISTANT)
#   GET  /opportunites              Lister (filtres : statut, domaine + pagination)
#   GET  /opportunites/{id}         Lire une opportunité
#   PUT  /opportunites/{id}         Remplacer une opportunité
#   DELETE /opportunites/{id}       Supprimer une opportunité
#   POST /opportunites/analyser     Analyser via IA (M3)
#
# ⚙️  Pagination : skip (défaut 0) + limit (défaut 100)
# ⚙️  Filtres GET : statut (EN_ATTENTE|ANALYSEE|ARCHIVEE), domaine
# ============================================================

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.dependencies import (
    get_current_user,
    require_role,
)
from app.database import get_db
from app.models.opportunite import Domaine, StatutOpportunite
from app.models.user import User
from app.repositories.opportunite_repository import OpportuniteRepository
from app.schemas.opportunite import (
    OpportuniteCreate,
    OpportuniteList,
    OpportuniteResponse,
    OpportuniteUpdate,
)
from app.services.opportunite_service import OpportuniteService

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
    status_code=status.HTTP_201_CREATED,
    summary="Créer une opportunité",
    description=(
        "Enregistre une nouvelle opportunité commerciale.\n\n"
        "**Rôles autorisés :** DIRECTION, ASSISTANT."
    ),
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
    response_model=OpportuniteList,
    summary="Lister les opportunités (avec filtres et pagination)",
    description=(
        "Retourne la liste des opportunités, triées par date de création décroissante.\n\n"
        "**Filtres optionnels :**\n"
        "- `statut` : `EN_ATTENTE` | `ANALYSEE` | `ARCHIVEE`\n"
        "- `domaine` : `IA` | `DEVOPS` | `CYBERSECURITE` | `GESTION` | `AUTRE` | …\n\n"
        "**Pagination :**\n"
        "- `skip` : nombre d'éléments à sauter (défaut : 0)\n"
        "- `limit` : nombre max d'éléments retournés (défaut : 100)\n\n"
        "**Exemple :** `GET /opportunites?statut=EN_ATTENTE&domaine=IA&skip=0&limit=20`\n\n"
        "Le champ `total` reflète le nombre d'éléments retournés (après filtres et pagination)."
    ),
)
def get_opportunites(
    statut: Optional[StatutOpportunite] = Query(default=None, description="Filtrer par statut"),
    domaine: Optional[Domaine] = Query(default=None, description="Filtrer par domaine"),
    skip: int = Query(default=0, ge=0, description="Nombre d'éléments à ignorer"),
    limit: int = Query(default=100, ge=1, le=500, description="Nombre max d'éléments"),
    service: OpportuniteService = Depends(get_opportunite_service),
    current_user: User = Depends(get_current_user),
):
    opportunites = service.get_all(statut=statut, domaine=domaine, skip=skip, limit=limit)

    return {
        "opportunites": opportunites,
        "total": len(opportunites)
    }

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
