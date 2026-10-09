from datetime import date as date_type
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session as DbSession

from app.core.dependencies import get_current_user, require_role
from app.database import get_db
from app.models.user import User
from app.schemas.formation import (
    InscriptionCreate,
    InscriptionResponse,
    ParticipantCreate,
    ParticipantResponse,
    ParticipantUpdate,
    PresenceCreate,
    PresenceResponse,
    PresenceUpdate,
    SeanceCreate,
    SeanceResponse,
    SeanceUpdate,
    SessionCreate,
    SessionResponse,
    SessionUpdate,
)
from app.services.formation_service import FormationService

router = APIRouter(prefix="/sessions", tags=["Formations"])
participants_router = APIRouter(prefix="/participants", tags=["Formations"])


def get_formation_service(db: DbSession = Depends(get_db)) -> FormationService:
    return FormationService(db)


# =============================================================================
# SESSIONS
# =============================================================================

@router.post("", response_model=SessionResponse, status_code=201)
def creer_session(
    data: SessionCreate,
    service: FormationService = Depends(get_formation_service),
    current_user: User = Depends(require_role("DIRECTION", "FORMATEUR")),
):
    return service.creer_session(data)


@router.get("", response_model=List[SessionResponse])
def lister_sessions(
    formateur_id: Optional[UUID] = Query(default=None),
    client: Optional[str] = Query(default=None),
    date_debut_min: Optional[date_type] = Query(default=None),
    date_debut_max: Optional[date_type] = Query(default=None),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=500),
    service: FormationService = Depends(get_formation_service),
    current_user: User = Depends(get_current_user),
):
    return service.lister_sessions(
        formateur_id=formateur_id,
        client=client,
        date_debut_min=date_debut_min,
        date_debut_max=date_debut_max,
        skip=skip,
        limit=limit,
    )


@router.get("/{session_id}", response_model=SessionResponse)
def get_session(
    session_id: UUID,
    service: FormationService = Depends(get_formation_service),
    current_user: User = Depends(get_current_user),
):
    return service.get_session(session_id)


@router.patch("/{session_id}", response_model=SessionResponse)
def mettre_a_jour_session(
    session_id: UUID,
    data: SessionUpdate,
    service: FormationService = Depends(get_formation_service),
    current_user: User = Depends(require_role("DIRECTION", "FORMATEUR")),
):
    return service.mettre_a_jour_session(session_id, data)


@router.delete("/{session_id}", status_code=204)
def supprimer_session(
    session_id: UUID,
    service: FormationService = Depends(get_formation_service),
    current_user: User = Depends(require_role("DIRECTION")),
):
    service.supprimer_session(session_id)


# =============================================================================
# SÉANCES D'UNE SESSION
# =============================================================================

@router.get("/{session_id}/seances", response_model=List[SeanceResponse])
def lister_seances(
    session_id: UUID,
    service: FormationService = Depends(get_formation_service),
    current_user: User = Depends(get_current_user),
):
    return service.lister_seances(session_id)


@router.post("/{session_id}/seances", response_model=SeanceResponse, status_code=201)
def ajouter_seance(
    session_id: UUID,
    data: SeanceCreate,
    service: FormationService = Depends(get_formation_service),
    current_user: User = Depends(require_role("DIRECTION", "FORMATEUR")),
):
    return service.ajouter_seance(session_id, data)


@router.patch("/seances/{seance_id}", response_model=SeanceResponse)
def mettre_a_jour_seance(
    seance_id: UUID,
    data: SeanceUpdate,
    service: FormationService = Depends(get_formation_service),
    current_user: User = Depends(require_role("DIRECTION", "FORMATEUR")),
):
    return service.mettre_a_jour_seance(seance_id, data)


@router.delete("/seances/{seance_id}", status_code=204)
def supprimer_seance(
    seance_id: UUID,
    service: FormationService = Depends(get_formation_service),
    current_user: User = Depends(require_role("DIRECTION", "FORMATEUR")),
):
    service.supprimer_seance(seance_id)


# =============================================================================
# PRÉSENCES
# =============================================================================

@router.get("/seances/{seance_id}/presences", response_model=List[PresenceResponse])
def lister_presences(
    seance_id: UUID,
    service: FormationService = Depends(get_formation_service),
    current_user: User = Depends(get_current_user),
):
    return service.lister_presences(seance_id)


@router.post("/seances/{seance_id}/presences", response_model=PresenceResponse, status_code=201)
def enregistrer_presence(
    seance_id: UUID,
    data: PresenceCreate,
    service: FormationService = Depends(get_formation_service),
    current_user: User = Depends(require_role("DIRECTION", "FORMATEUR")),
):
    return service.enregistrer_presence(seance_id, data)


@router.patch("/seances/presences/{presence_id}", response_model=PresenceResponse)
def mettre_a_jour_presence(
    presence_id: UUID,
    data: PresenceUpdate,
    service: FormationService = Depends(get_formation_service),
    current_user: User = Depends(require_role("DIRECTION", "FORMATEUR")),
):
    return service.mettre_a_jour_presence(presence_id, data)


# =============================================================================
# INSCRIPTIONS
# =============================================================================

@router.post("/{session_id}/inscrire", response_model=InscriptionResponse, status_code=201)
def inscrire_participant(
    session_id: UUID,
    data: InscriptionCreate,
    service: FormationService = Depends(get_formation_service),
    current_user: User = Depends(require_role("DIRECTION", "FORMATEUR")),
):
    return service.inscrire_participant(session_id, data)


@router.delete("/{session_id}/inscrire/{participant_id}", status_code=204)
def desinscrire_participant(
    session_id: UUID,
    participant_id: UUID,
    service: FormationService = Depends(get_formation_service),
    current_user: User = Depends(require_role("DIRECTION", "FORMATEUR")),
):
    service.desinscrire_participant(session_id, participant_id)


@router.get("/{session_id}/participants", response_model=List[ParticipantResponse])
def lister_participants_session(
    session_id: UUID,
    service: FormationService = Depends(get_formation_service),
    current_user: User = Depends(get_current_user),
):
    return service.lister_participants_session(session_id)


# =============================================================================
# PARTICIPANTS (ressource indépendante)
# =============================================================================

@participants_router.post("", response_model=ParticipantResponse, status_code=201)
def creer_participant(
    data: ParticipantCreate,
    service: FormationService = Depends(get_formation_service),
    current_user: User = Depends(require_role("DIRECTION", "FORMATEUR", "ASSISTANT")),
):
    return service.creer_participant(data)


@participants_router.get("", response_model=List[ParticipantResponse])
def lister_participants(
    nom: Optional[str] = Query(default=None),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=500),
    service: FormationService = Depends(get_formation_service),
    current_user: User = Depends(get_current_user),
):
    return service.lister_participants(nom=nom, skip=skip, limit=limit)


@participants_router.get("/{participant_id}", response_model=ParticipantResponse)
def get_participant(
    participant_id: UUID,
    service: FormationService = Depends(get_formation_service),
    current_user: User = Depends(get_current_user),
):
    return service.get_participant(participant_id)


@participants_router.patch("/{participant_id}", response_model=ParticipantResponse)
def mettre_a_jour_participant(
    participant_id: UUID,
    data: ParticipantUpdate,
    service: FormationService = Depends(get_formation_service),
    current_user: User = Depends(require_role("DIRECTION", "FORMATEUR", "ASSISTANT")),
):
    return service.mettre_a_jour_participant(participant_id, data)


@participants_router.delete("/{participant_id}", status_code=204)
def supprimer_participant(
    participant_id: UUID,
    service: FormationService = Depends(get_formation_service),
    current_user: User = Depends(require_role("DIRECTION")),
):
    service.supprimer_participant(participant_id)