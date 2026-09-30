# app/api/v1/endpoints/facture.py
# ============================================================
# ROUTES BACKEND — Facturation
# ============================================================
#
#   POST /factures                        Émettre une facture (DIRECTION, COMPTABLE)
#   GET  /factures                        Lister (filtres : statut, client + pagination)
#   GET  /factures/{id}                   Lire une facture
#   PATCH /factures/{id}                  Mettre à jour partielle (PATCH)
#   POST /factures/{id}/paiments          Ajouter un paiement
#   POST /factures/{id}/relance           Générer un texte de relance simple
#   POST /factures/{id}/relances          Enregistrer une relance IA HITL
#   GET  /factures/{id}/relances          Lister les relances IA d'une facture
#   DELETE /factures/{id}                 Supprimer une facture (DIRECTION uniquement)
#
# ⚙️  Pagination GET : skip (défaut 0) + limit (défaut 100)
# ⚙️  Filtres GET : statut (EMISE|PARTIELLEMENT_PAYEE|PAYEE|EN_RETARD), client (recherche partielle)
# ============================================================

from typing import List, Optional
from uuid import UUID
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.core.dependencies import get_current_user, require_role
from app.models.facture import StatutFacture
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


@router.get(
    "",
    response_model=List[FactureResponse],
    summary="Lister les factures (avec filtres et pagination)",
    description=(
        "Retourne la liste des factures, triées par date de création décroissante.\n\n"
        "**Filtres optionnels :**\n"
        "- `statut` : `EMISE` | `PARTIELLEMENT_PAYEE` | `PAYEE` | `EN_RETARD`\n"
        "- `client` : recherche partielle (insensible à la casse)\n\n"
        "**Pagination :**\n"
        "- `skip` : nombre d'éléments à sauter (défaut : 0)\n"
        "- `limit` : nombre max d'éléments retournés (défaut : 100)\n\n"
        "**Exemple :** `GET /factures?statut=EN_RETARD&client=SONAPAR&skip=0&limit=20`"
    ),
)
def lister_factures(
    statut: Optional[StatutFacture] = Query(default=None, description="Filtrer par statut"),
    client: Optional[str] = Query(default=None, description="Recherche partielle sur le nom du client"),
    skip: int = Query(default=0, ge=0, description="Nombre d'éléments à ignorer"),
    limit: int = Query(default=100, ge=1, le=500, description="Nombre max d'éléments"),
    service: FactureService = Depends(get_facture_service),
    current_user: User = Depends(get_current_user),
):
    return service.lister(statut=statut, client=client, skip=skip, limit=limit)


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


@router.delete(
    "/{facture_id}",
    status_code=204,
    summary="Supprimer une facture",
    description=(
        "Supprime définitivement une facture et toutes ses données associées "
        "(paiements, relances IA). Irréversible.\n\n"
        "Retourne **404** si la facture n'existe pas.\n\n"
        "**Rôle autorisé :** DIRECTION uniquement."
    ),
)
def supprimer_facture(
    facture_id: UUID,
    service: FactureService = Depends(get_facture_service),
    current_user: User = Depends(require_role("DIRECTION")),
):
    service.supprimer_facture(facture_id)