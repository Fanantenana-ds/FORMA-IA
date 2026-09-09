from uuid import UUID
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session as DbSession

from app.database import get_db
from app.core.dependencies import get_current_user, require_role
from app.models.user import User
from app.schemas.formation import (
    SeanceCreate, SeanceResponse,
    SessionCreate, SessionResponse,
    ParticipantCreate, ParticipantResponse,
    PresenceCreate, PresenceResponse
)
from app.services.formation_service import FormationService

router = APIRouter(
    prefix="/sessions",
    tags=["Formations"]
)

def get_formation_service(db: DbSession = Depends(get_db)) -> FormationService:
    return FormationService(db)


@router.post("", response_model=SessionResponse, status_code=201)
def creer_session(
    data: SessionCreate,
    service: FormationService = Depends(get_formation_service),
    current_user: User = Depends(require_role("DIRECTION", "FORMATEUR"))
):
    return service.creer_session(data)


@router.get("/{session_id}", response_model=SessionResponse)
def get_session(
    session_id: UUID,
    service: FormationService = Depends(get_formation_service),
    current_user: User = Depends(get_current_user)
):
    return service.get_session(session_id)


@router.post("/{session_id}/seances", response_model=SeanceResponse, status_code=201)
def ajouter_seance(
    session_id: UUID,
    data: SeanceCreate,
    service: FormationService = Depends(get_formation_service),
    current_user: User = Depends(require_role("DIRECTION", "FORMATEUR"))
):
    return service.ajouter_seance(session_id, data)


@router.post("/seances/{seance_id}/presences", response_model=PresenceResponse, status_code=201)
def enregistrer_presence(
    seance_id: UUID,
    data: PresenceCreate,
    service: FormationService = Depends(get_formation_service),
    current_user: User = Depends(require_role("DIRECTION", "FORMATEUR"))
):
    return service.enregistrer_presence(seance_id, data)


participants_router = APIRouter(
    prefix="/participants",
    tags=["Formations"]
)

@participants_router.post("", response_model=ParticipantResponse, status_code=201)
def creer_participant(
    data: ParticipantCreate,
    service: FormationService = Depends(get_formation_service),
    current_user: User = Depends(require_role("DIRECTION", "FORMATEUR", "ASSISTANT"))
):
    return service.creer_participant(data)