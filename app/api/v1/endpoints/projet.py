# app/api/v1/endpoints/projet.py
# ============================================================
# ROUTES BACKEND — Préparation (Étape 3 CDC)
# Salles, Projets, EDT, Budget
# ============================================================
#   POST   /salles                    Créer une salle
#   GET    /salles                    Lister les salles
#   GET    /salles/{id}               Lire une salle
#   PATCH  /salles/{id}               Mise à jour partielle
#   DELETE /salles/{id}               Supprimer
#
#   POST   /projets                   Créer un projet
#   GET    /projets                   Lister les projets
#   GET    /projets/{id}              Lire un projet
#   PATCH  /projets/{id}              Mise à jour partielle
#   DELETE /projets/{id}              Supprimer (cascade EDT + budget)
#
#   POST   /projets/{id}/edt          Ajouter une séance EDT
#   GET    /projets/{id}/edt          Lister l'EDT d'un projet
#   DELETE /projets/{id}/edt/{edt_id} Supprimer une séance
#
#   POST   /projets/{id}/budget       Créer ou remplacer le budget
#   GET    /projets/{id}/budget       Lire le budget
# ============================================================

from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.core.dependencies import get_current_user, require_role
from app.models.projet import StatutProjet
from app.models.user import User
from app.schemas.projet import (
    SalleCreate, SalleUpdate, SalleReplace, SalleResponse,
    ProjetCreate, ProjetUpdate, ProjetReplace, ProjetResponse,
    EdtSessionCreate, EdtSessionResponse,
    BudgetCreate, BudgetResponse,
)
from app.services.projet_service import SalleService, ProjetService

salles_router = APIRouter(prefix="/salles", tags=["Préparation — Salles"])
projets_router = APIRouter(prefix="/projets", tags=["Préparation — Projets"])


def get_salle_service(db: Session = Depends(get_db)) -> SalleService:
    return SalleService(db)


def get_projet_service(db: Session = Depends(get_db)) -> ProjetService:
    return ProjetService(db)


# ============================================================
# SALLES
# ============================================================

@salles_router.post(
    "",
    response_model=SalleResponse,
    status_code=201,
    summary="Créer une salle de formation",
    description="**Rôles :** DIRECTION, ASSISTANT.",
)
def creer_salle(
    data: SalleCreate,
    service: SalleService = Depends(get_salle_service),
    current_user: User = Depends(require_role("DIRECTION", "ASSISTANT")),
):
    return service.creer(data)


@salles_router.get(
    "",
    response_model=List[SalleResponse],
    summary="Lister les salles",
    description="Filtre optionnel : `disponible=true|false`.",
)
def lister_salles(
    disponible: Optional[bool] = Query(default=None),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=500),
    service: SalleService = Depends(get_salle_service),
    current_user: User = Depends(get_current_user),
):
    return service.lister(disponible=disponible, skip=skip, limit=limit)


@salles_router.get("/{salle_id}", response_model=SalleResponse, summary="Lire une salle")
def get_salle(
    salle_id: UUID,
    service: SalleService = Depends(get_salle_service),
    current_user: User = Depends(get_current_user),
):
    return service.get(salle_id)


@salles_router.put(
    "/{salle_id}",
    response_model=SalleResponse,
    summary="Remplacer une salle (PUT complet)",
    description=(
        "Remplacement complet de la salle : tous les champs sont écrasés. "
        "Utilisez **PATCH** pour ne modifier qu'un champ.\n\n"
        "**Rôles :** DIRECTION, ASSISTANT."
    ),
)
def remplacer_salle(
    salle_id: UUID,
    data: SalleReplace,
    service: SalleService = Depends(get_salle_service),
    current_user: User = Depends(require_role("DIRECTION", "ASSISTANT")),
):
    return service.remplacer(salle_id, data)


@salles_router.patch(
    "/{salle_id}",
    response_model=SalleResponse,
    summary="Mettre à jour une salle (PATCH partiel)",
    description="**Rôles :** DIRECTION, ASSISTANT.",
)
def mettre_a_jour_salle(
    salle_id: UUID,
    data: SalleUpdate,
    service: SalleService = Depends(get_salle_service),
    current_user: User = Depends(require_role("DIRECTION", "ASSISTANT")),
):
    return service.mettre_a_jour(salle_id, data)


@salles_router.delete(
    "/{salle_id}",
    status_code=204,
    summary="Supprimer une salle",
    description="**Rôle :** DIRECTION uniquement.",
)
def supprimer_salle(
    salle_id: UUID,
    service: SalleService = Depends(get_salle_service),
    current_user: User = Depends(require_role("DIRECTION")),
):
    service.supprimer(salle_id)


# ============================================================
# PROJETS
# ============================================================

@projets_router.post(
    "",
    response_model=ProjetResponse,
    status_code=201,
    summary="Créer un projet de formation",
    description=(
        "Un projet regroupe une formation à venir : titre, client, dates, "
        "statut. Les séances EDT et le budget sont ajoutés via les sous-routes.\n\n"
        "**Rôles :** DIRECTION, ASSISTANT."
    ),
)
def creer_projet(
    data: ProjetCreate,
    service: ProjetService = Depends(get_projet_service),
    current_user: User = Depends(require_role("DIRECTION", "ASSISTANT")),
):
    return service.creer(data)


@projets_router.get(
    "",
    response_model=List[ProjetResponse],
    summary="Lister les projets",
    description="Filtre optionnel : `statut` (BROUILLON|EN_COURS|VALIDE|TERMINE|ANNULE).",
)
def lister_projets(
    statut: Optional[StatutProjet] = Query(default=None),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=500),
    service: ProjetService = Depends(get_projet_service),
    current_user: User = Depends(get_current_user),
):
    return service.lister(statut=statut, skip=skip, limit=limit)


@projets_router.get("/{projet_id}", response_model=ProjetResponse, summary="Lire un projet")
def get_projet(
    projet_id: UUID,
    service: ProjetService = Depends(get_projet_service),
    current_user: User = Depends(get_current_user),
):
    return service.get(projet_id)


@projets_router.put(
    "/{projet_id}",
    response_model=ProjetResponse,
    summary="Remplacer un projet (PUT complet)",
    description=(
        "Remplacement complet du projet : tous les champs sont écrasés. "
        "Utilisez **PATCH** pour ne modifier qu'un champ.\n\n"
        "**Rôles :** DIRECTION, ASSISTANT."
    ),
)
def remplacer_projet(
    projet_id: UUID,
    data: ProjetReplace,
    service: ProjetService = Depends(get_projet_service),
    current_user: User = Depends(require_role("DIRECTION", "ASSISTANT")),
):
    return service.remplacer(projet_id, data)


@projets_router.patch(
    "/{projet_id}",
    response_model=ProjetResponse,
    summary="Mettre à jour un projet (PATCH partiel)",
    description="**Rôles :** DIRECTION, ASSISTANT.",
)
def mettre_a_jour_projet(
    projet_id: UUID,
    data: ProjetUpdate,
    service: ProjetService = Depends(get_projet_service),
    current_user: User = Depends(require_role("DIRECTION", "ASSISTANT")),
):
    return service.mettre_a_jour(projet_id, data)


@projets_router.delete(
    "/{projet_id}",
    status_code=204,
    summary="Supprimer un projet (cascade EDT + budget)",
    description="**Rôle :** DIRECTION uniquement.",
)
def supprimer_projet(
    projet_id: UUID,
    service: ProjetService = Depends(get_projet_service),
    current_user: User = Depends(require_role("DIRECTION")),
):
    service.supprimer(projet_id)


# ── EDT ─────────────────────────────────────────────────────

@projets_router.post(
    "/{projet_id}/edt",
    response_model=EdtSessionResponse,
    status_code=201,
    summary="Ajouter une séance à l'emploi du temps",
    description="**Rôles :** DIRECTION, ASSISTANT.",
)
def ajouter_edt(
    projet_id: UUID,
    data: EdtSessionCreate,
    service: ProjetService = Depends(get_projet_service),
    current_user: User = Depends(require_role("DIRECTION", "ASSISTANT")),
):
    return service.ajouter_edt(projet_id, data)


@projets_router.get(
    "/{projet_id}/edt",
    response_model=List[EdtSessionResponse],
    summary="Lister l'emploi du temps d'un projet",
)
def lister_edt(
    projet_id: UUID,
    service: ProjetService = Depends(get_projet_service),
    current_user: User = Depends(get_current_user),
):
    return service.lister_edt(projet_id)


@projets_router.delete(
    "/{projet_id}/edt/{edt_id}",
    status_code=204,
    summary="Supprimer une séance de l'EDT",
    description="**Rôles :** DIRECTION, ASSISTANT.",
)
def supprimer_edt(
    projet_id: UUID,
    edt_id: UUID,
    service: ProjetService = Depends(get_projet_service),
    current_user: User = Depends(require_role("DIRECTION", "ASSISTANT")),
):
    service.supprimer_edt(projet_id, edt_id)


# ── Budget ──────────────────────────────────────────────────

@projets_router.post(
    "/{projet_id}/budget",
    response_model=BudgetResponse,
    status_code=201,
    summary="Créer ou remplacer le budget d'un projet",
    description=(
        "Idempotent : si un budget existe déjà, il est remplacé.\n\n"
        "`cout_total` est calculé automatiquement : `formateur + salle + supports`.\n\n"
        "Mettre `valide=true` enregistre l'ID du valideur (utilisateur courant).\n\n"
        "**Rôles :** DIRECTION, ASSISTANT."
    ),
)
def creer_budget(
    projet_id: UUID,
    data: BudgetCreate,
    service: ProjetService = Depends(get_projet_service),
    current_user: User = Depends(require_role("DIRECTION", "ASSISTANT")),
):
    return service.creer_ou_maj_budget(projet_id, data, valideur_id=current_user.id)


@projets_router.get(
    "/{projet_id}/budget",
    response_model=BudgetResponse,
    summary="Lire le budget d'un projet",
)
def get_budget(
    projet_id: UUID,
    service: ProjetService = Depends(get_projet_service),
    current_user: User = Depends(get_current_user),
):
    return service.get_budget(projet_id)
