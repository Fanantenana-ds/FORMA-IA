# app/api/v1/endpoints/rh.py
# ============================================================
# ROUTES BACKEND — M4 RH (CRUD Formateurs, Candidats, Entretiens)
# ============================================================

from uuid import UUID
from typing import List, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.core.dependencies import get_current_user, require_role
from app.models.user import User
from app.schemas.rh import (
    FormateurCreate, FormateurUpdate, FormateurResponse,
    CandidatCreate, CandidatUpdate, CandidatResponse,
    EntretienCreate, EntretienUpdate, EntretienResponse,
)
from app.services.rh_service import RhService

router = APIRouter(prefix="/rh", tags=["M4 — RH Backend"])


def get_rh_service(db: Session = Depends(get_db)) -> RhService:
    return RhService(db)


# =============================================================================
# FORMATEURS
# =============================================================================

@router.post("/formateurs", response_model=FormateurResponse, status_code=201,
             summary="Créer un formateur externe")
def creer_formateur(
    data: FormateurCreate,
    service: RhService = Depends(get_rh_service),
    current_user: User = Depends(require_role("DIRECTION", "ADMIN")),
):
    return service.creer_formateur(data)


@router.get("/formateurs", response_model=List[FormateurResponse],
            summary="Lister les formateurs")
def lister_formateurs(
    specialite: Optional[str] = Query(default=None),
    statut: Optional[str] = Query(default=None),
    service: RhService = Depends(get_rh_service),
    current_user: User = Depends(get_current_user),
):
    return service.lister_formateurs(specialite=specialite, statut=statut)


@router.get("/formateurs/{formateur_id}", response_model=FormateurResponse,
            summary="Lire un formateur")
def get_formateur(
    formateur_id: UUID,
    service: RhService = Depends(get_rh_service),
    current_user: User = Depends(get_current_user),
):
    return service.get_formateur(formateur_id)


@router.patch("/formateurs/{formateur_id}", response_model=FormateurResponse,
              summary="Mettre à jour un formateur (score, statut, tarif...)")
def mettre_a_jour_formateur(
    formateur_id: UUID,
    data: FormateurUpdate,
    service: RhService = Depends(get_rh_service),
    current_user: User = Depends(require_role("DIRECTION", "ADMIN")),
):
    return service.mettre_a_jour_formateur(formateur_id, data)


@router.delete("/formateurs/{formateur_id}", status_code=204,
               summary="Supprimer un formateur")
def supprimer_formateur(
    formateur_id: UUID,
    service: RhService = Depends(get_rh_service),
    current_user: User = Depends(require_role("DIRECTION", "ADMIN")),
):
    service.supprimer_formateur(formateur_id)


# =============================================================================
# CANDIDATS
# =============================================================================

@router.post("/candidats", response_model=CandidatResponse, status_code=201,
             summary="Créer un dossier candidat")
def creer_candidat(
    data: CandidatCreate,
    service: RhService = Depends(get_rh_service),
    current_user: User = Depends(require_role("DIRECTION", "ADMIN")),
):
    return service.creer_candidat(data)


@router.get("/candidats", response_model=List[CandidatResponse],
            summary="Lister les candidats")
def lister_candidats(
    poste_vise: Optional[str] = Query(default=None),
    decision: Optional[str] = Query(default=None),
    service: RhService = Depends(get_rh_service),
    current_user: User = Depends(get_current_user),
):
    return service.lister_candidats(poste_vise=poste_vise, decision=decision)


@router.get("/candidats/{candidat_id}", response_model=CandidatResponse,
            summary="Lire un dossier candidat")
def get_candidat(
    candidat_id: UUID,
    service: RhService = Depends(get_rh_service),
    current_user: User = Depends(get_current_user),
):
    return service.get_candidat(candidat_id)


@router.patch("/candidats/{candidat_id}", response_model=CandidatResponse,
              summary="Mettre à jour un dossier candidat (décision, review_id...)")
def mettre_a_jour_candidat(
    candidat_id: UUID,
    data: CandidatUpdate,
    service: RhService = Depends(get_rh_service),
    current_user: User = Depends(require_role("DIRECTION", "ADMIN")),
):
    return service.mettre_a_jour_candidat(candidat_id, data)


# =============================================================================
# ENTRETIENS (sous-ressource de Candidat)
# =============================================================================

@router.post("/candidats/{candidat_id}/entretiens",
             response_model=EntretienResponse, status_code=201,
             summary="Créer un entretien pour un candidat")
def creer_entretien(
    candidat_id: UUID,
    data: EntretienCreate,
    service: RhService = Depends(get_rh_service),
    current_user: User = Depends(require_role("DIRECTION", "ADMIN")),
):
    return service.creer_entretien(candidat_id, data)


@router.get("/candidats/{candidat_id}/entretiens",
            response_model=List[EntretienResponse],
            summary="Lister les entretiens d'un candidat")
def lister_entretiens(
    candidat_id: UUID,
    service: RhService = Depends(get_rh_service),
    current_user: User = Depends(get_current_user),
):
    return service.lister_entretiens(candidat_id)


@router.patch("/entretiens/{entretien_id}", response_model=EntretienResponse,
              summary="Mettre à jour un entretien (CR, email, décision...)")
def mettre_a_jour_entretien(
    entretien_id: UUID,
    data: EntretienUpdate,
    service: RhService = Depends(get_rh_service),
    current_user: User = Depends(require_role("DIRECTION", "ADMIN")),
):
    return service.mettre_a_jour_entretien(entretien_id, data)
