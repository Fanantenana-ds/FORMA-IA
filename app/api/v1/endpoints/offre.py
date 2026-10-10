# app/api/v1/endpoints/offre.py
# ============================================================
# ROUTES BACKEND — Offres techniques et financières (Étape 2 CDC)
# ============================================================
#   POST   /offres                  Créer une offre (DIRECTION, ASSISTANT)
#   GET    /offres                  Lister (filtres : statut, client, opportunite_id)
#   GET    /offres/{id}             Lire une offre
#   PATCH  /offres/{id}             Mise à jour partielle (PATCH)
#   DELETE /offres/{id}             Supprimer (DIRECTION uniquement)
# ============================================================

from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user, require_role
from app.database import get_db
from app.models.offre import StatutOffre
from app.models.user import User
from app.schemas.offre import OffreCreate, OffreReplace, OffreResponse, OffreUpdate
from app.services.offre_service import OffreService

router = APIRouter(prefix="/offres", tags=["Offres"])


def get_service(db: Session = Depends(get_db)) -> OffreService:
    return OffreService(db)


@router.post(
    "",
    response_model=OffreResponse,
    status_code=201,
    summary="Créer une offre",
    description=(
        "Crée une nouvelle offre technique/financière. Les champs `trame_technique` et "
        "`trame_financiere` sont remplis ultérieurement par les routes IA "
        "(`POST /ia/offres/generer-technique` et `/ia/offres/generer-financiere`).\n\n"
        "**Rôles :** DIRECTION, ASSISTANT."
    ),
)
def creer_offre(
    data: OffreCreate,
    service: OffreService = Depends(get_service),
    current_user: User = Depends(require_role("DIRECTION", "ASSISTANT")),
):
    return service.creer(data)


@router.get(
    "",
    response_model=list[OffreResponse],
    summary="Lister les offres (avec filtres et pagination)",
    description=(
        "**Filtres optionnels :** `statut`, `client` (recherche partielle), `opportunite_id`.\n\n"
        "**Pagination :** `skip` (défaut 0) + `limit` (défaut 100, max 500)."
    ),
)
def lister_offres(
    statut: Optional[StatutOffre] = Query(default=None),
    client: Optional[str] = Query(default=None),
    opportunite_id: Optional[UUID] = Query(default=None),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=500),
    service: OffreService = Depends(get_service),
    current_user: User = Depends(get_current_user),
):
    return service.lister(statut=statut, client=client, opportunite_id=opportunite_id, skip=skip, limit=limit)


@router.get(
    "/{offre_id}",
    response_model=OffreResponse,
    summary="Lire une offre",
)
def get_offre(
    offre_id: UUID,
    service: OffreService = Depends(get_service),
    current_user: User = Depends(get_current_user),
):
    return service.get(offre_id)


@router.put(
    "/{offre_id}",
    response_model=OffreResponse,
    summary="Remplacer une offre (PUT complet)",
    description=(
        "Remplacement complet de l'offre : tous les champs sont écrasés avec les valeurs "
        "fournies. Les champs non envoyés reviennent à leur valeur par défaut.\n\n"
        "Utilisez **PATCH** pour ne modifier qu'un ou deux champs.\n\n"
        "**Rôles :** DIRECTION, ASSISTANT."
    ),
)
def remplacer_offre(
    offre_id: UUID,
    data: OffreReplace,
    service: OffreService = Depends(get_service),
    current_user: User = Depends(require_role("DIRECTION", "ASSISTANT")),
):
    return service.remplacer(offre_id, data)


@router.patch(
    "/{offre_id}",
    response_model=OffreResponse,
    summary="Mettre à jour une offre (PATCH partiel)",
    description=(
        "Modifie un ou plusieurs champs. Tous les champs sont optionnels (PATCH semantics).\n\n"
        "Permet notamment de passer le statut à `ENVOYEE`, `ACCEPTEE` ou `REFUSEE`.\n\n"
        "**Rôles :** DIRECTION, ASSISTANT."
    ),
)
def mettre_a_jour_offre(
    offre_id: UUID,
    data: OffreUpdate,
    service: OffreService = Depends(get_service),
    current_user: User = Depends(require_role("DIRECTION", "ASSISTANT")),
):
    return service.mettre_a_jour(offre_id, data)


@router.delete(
    "/{offre_id}",
    status_code=204,
    summary="Supprimer une offre",
    description="Suppression définitive. **Rôle :** DIRECTION uniquement.",
)
def supprimer_offre(
    offre_id: UUID,
    service: OffreService = Depends(get_service),
    current_user: User = Depends(require_role("DIRECTION")),
):
    service.supprimer(offre_id)
