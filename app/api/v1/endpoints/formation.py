from datetime import date as date_type
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session as DbSession

from app.core.dependencies import get_current_user, require_role
from app.database import get_db
from app.models.user import User
from app.models.formation import Inscription, Participant, Seance, Session as TrainingSession
from app.models.rh import Formateur
from app.models.user import RoleEnum
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


def _trainer_for_user(db: DbSession, current_user: User):
    if current_user.role != RoleEnum.FORMATEUR:
        return None
    return db.query(Formateur).filter(Formateur.user_id == current_user.id).first()


def _assert_trainer_session_access(db: DbSession, session_id: UUID, current_user: User) -> None:
    trainer = _trainer_for_user(db, current_user)
    if trainer is None:
        if current_user.role == RoleEnum.FORMATEUR:
            raise HTTPException(status_code=404, detail="Aucune fiche formateur n’est associée à ce compte.")
        return
    session = db.query(TrainingSession).filter(TrainingSession.id == session_id).first()
    if session is None or session.formateur_id != trainer.id:
        raise HTTPException(status_code=404, detail="Session introuvable pour ce compte formateur.")


# =============================================================================
# SESSIONS
# =============================================================================

@router.post("", response_model=SessionResponse, status_code=201)
def creer_session(
    data: SessionCreate,
    service: FormationService = Depends(get_formation_service),
    current_user: User = Depends(require_role("DIRECTION")),
):
    return service.creer_session(data)


@router.get("", response_model=list[SessionResponse])
def lister_sessions(
    formateur_id: UUID | None = Query(default=None),
    client: str | None = Query(default=None),
    date_debut_min: date_type | None = Query(default=None),
    date_debut_max: date_type | None = Query(default=None),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=500),
    service: FormationService = Depends(get_formation_service),
    current_user: User = Depends(get_current_user),
):
    if current_user.role == RoleEnum.FORMATEUR:
        trainer = _trainer_for_user(service.db, current_user)
        if trainer is None:
            return []
        formateur_id = trainer.id
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
    _assert_trainer_session_access(service.db, session_id, current_user)
    return service.get_session(session_id)


@router.get("/evaluations/satisfaction")
def lister_retours_satisfaction(
    db: DbSession = Depends(get_db),
    current_user: User = Depends(require_role("DIRECTION", "ADMIN", "ASSISTANT")),
):
    """Survey responses used by the trainer evaluation view."""
    rows = (db.query(Inscription, Participant, TrainingSession, Formateur)
            .join(Participant, Participant.id == Inscription.participant_id)
            .join(TrainingSession, TrainingSession.id == Inscription.session_id)
            .outerjoin(Formateur, Formateur.id == TrainingSession.formateur_id)
            .filter(Inscription.reponses_satisfaction.isnot(None))
            .order_by(Inscription.date_evaluation_finale.desc())
            .limit(1000).all())
    return [{
        "session_id": str(session.id), "session_titre": session.titre,
        "formateur_id": str(formateur.id) if formateur else None,
        "formateur_nom": " ".join(part for part in [formateur.prenom, formateur.nom] if part) if formateur else "Formateur non affecté",
        "participant_id": str(participant.id), "participant_nom": " ".join(part for part in [participant.prenom, participant.nom] if part),
        "score_satisfaction": inscription.score_satisfaction,
        "niveau_initial": inscription.niveau_initial, "niveau_final": inscription.niveau_final,
        "score_test_final": inscription.score_test_final,
        "reponses_satisfaction": inscription.reponses_satisfaction or [],
        "date_evaluation": inscription.date_evaluation_finale.isoformat() if inscription.date_evaluation_finale else None,
    } for inscription, participant, session, formateur in rows]


@router.patch("/{session_id}", response_model=SessionResponse)
def mettre_a_jour_session(
    session_id: UUID,
    data: SessionUpdate,
    service: FormationService = Depends(get_formation_service),
    current_user: User = Depends(require_role("DIRECTION")),
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

@router.get("/{session_id}/seances", response_model=list[SeanceResponse])
def lister_seances(
    session_id: UUID,
    service: FormationService = Depends(get_formation_service),
    current_user: User = Depends(get_current_user),
):
    _assert_trainer_session_access(service.db, session_id, current_user)
    return service.lister_seances(session_id)


@router.post("/{session_id}/seances", response_model=SeanceResponse, status_code=201)
def ajouter_seance(
    session_id: UUID,
    data: SeanceCreate,
    service: FormationService = Depends(get_formation_service),
    current_user: User = Depends(require_role("DIRECTION", "FORMATEUR")),
):
    if current_user.role == RoleEnum.FORMATEUR:
        _assert_trainer_session_access(service.db, session_id, current_user)
        trainer = _trainer_for_user(service.db, current_user)
        if trainer is None:
            raise HTTPException(status_code=404, detail="Aucune fiche formateur n’est associée à ce compte.")
        data.formateur_id = trainer.id
    return service.ajouter_seance(session_id, data)


@router.patch("/seances/{seance_id}", response_model=SeanceResponse)
def mettre_a_jour_seance(
    seance_id: UUID,
    data: SeanceUpdate,
    service: FormationService = Depends(get_formation_service),
    current_user: User = Depends(require_role("DIRECTION")),
):
    return service.mettre_a_jour_seance(seance_id, data)


@router.delete("/seances/{seance_id}", status_code=204)
def supprimer_seance(
    seance_id: UUID,
    service: FormationService = Depends(get_formation_service),
    current_user: User = Depends(require_role("DIRECTION")),
):
    service.supprimer_seance(seance_id)


# =============================================================================
# PRÉSENCES
# =============================================================================

@router.get("/seances/{seance_id}/presences", response_model=list[PresenceResponse])
def lister_presences(
    seance_id: UUID,
    service: FormationService = Depends(get_formation_service),
    current_user: User = Depends(get_current_user),
):
    seance = service.db.query(Seance).filter(Seance.id == seance_id).first()
    if seance is None:
        raise HTTPException(status_code=404, detail="Séance introuvable.")
    _assert_trainer_session_access(service.db, seance.session_id, current_user)
    return service.lister_presences(seance_id)


@router.post("/seances/{seance_id}/presences", response_model=PresenceResponse, status_code=201)
def enregistrer_presence(
    seance_id: UUID,
    data: PresenceCreate,
    service: FormationService = Depends(get_formation_service),
    current_user: User = Depends(require_role("DIRECTION")),
):
    return service.enregistrer_presence(seance_id, data)


@router.patch("/seances/presences/{presence_id}", response_model=PresenceResponse)
def mettre_a_jour_presence(
    presence_id: UUID,
    data: PresenceUpdate,
    service: FormationService = Depends(get_formation_service),
    current_user: User = Depends(require_role("DIRECTION")),
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
    current_user: User = Depends(require_role("DIRECTION")),
):
    return service.inscrire_participant(session_id, data)


@router.delete("/{session_id}/inscrire/{participant_id}", status_code=204)
def desinscrire_participant(
    session_id: UUID,
    participant_id: UUID,
    service: FormationService = Depends(get_formation_service),
    current_user: User = Depends(require_role("DIRECTION")),
):
    service.desinscrire_participant(session_id, participant_id)


@router.get("/{session_id}/participants")
def lister_participants_session(
    session_id: UUID,
    db: DbSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _assert_trainer_session_access(db, session_id, current_user)
    rows = (
        db.query(Inscription, Participant)
        .join(Participant, Participant.id == Inscription.participant_id)
        .filter(Inscription.session_id == session_id)
        .order_by(Inscription.date_inscription.desc())
        .all()
    )
    return [{
        "id": str(participant.id),
        "nom": participant.nom,
        "prenom": participant.prenom,
        "email": participant.email,
        "entreprise": participant.entreprise,
        "poste": inscription.poste,
        "niveau_initial": inscription.niveau_initial,
        "score_positionnement": inscription.score_positionnement,
        "niveau_final": inscription.niveau_final,
        "score_test_final": inscription.score_test_final,
        "score_satisfaction": inscription.score_satisfaction,
        "date_evaluation_finale": inscription.date_evaluation_finale.isoformat() if inscription.date_evaluation_finale else None,
        "date_inscription": inscription.date_inscription.isoformat() if inscription.date_inscription else None,
    } for inscription, participant in rows]


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


@participants_router.get("", response_model=list[ParticipantResponse])
def lister_participants(
    nom: str | None = Query(default=None),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=500),
    service: FormationService = Depends(get_formation_service),
    current_user: User = Depends(get_current_user),
):
    if current_user.role == RoleEnum.FORMATEUR:
        trainer = _trainer_for_user(service.db, current_user)
        if trainer is None:
            return []
        query = (
            service.db.query(Participant)
            .join(Inscription, Inscription.participant_id == Participant.id)
            .join(TrainingSession, TrainingSession.id == Inscription.session_id)
            .filter(TrainingSession.formateur_id == trainer.id)
            .distinct()
        )
        if nom:
            query = query.filter(Participant.nom.ilike(f"%{nom}%"))
        return query.order_by(Participant.nom).offset(skip).limit(limit).all()
    return service.lister_participants(nom=nom, skip=skip, limit=limit)


@participants_router.get("/{participant_id}", response_model=ParticipantResponse)
def get_participant(
    participant_id: UUID,
    service: FormationService = Depends(get_formation_service),
    current_user: User = Depends(get_current_user),
):
    participant = service.get_participant(participant_id)
    if current_user.role == RoleEnum.FORMATEUR:
        trainer = _trainer_for_user(service.db, current_user)
        enrolled = service.db.query(Inscription).join(TrainingSession, TrainingSession.id == Inscription.session_id).filter(
            Inscription.participant_id == participant_id,
            TrainingSession.formateur_id == (trainer.id if trainer else None),
        ).first()
        if not enrolled:
            raise HTTPException(status_code=404, detail="Participant introuvable pour vos sessions.")
    return participant


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
