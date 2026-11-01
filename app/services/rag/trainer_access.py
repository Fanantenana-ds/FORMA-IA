"""Tenant and session scoped access for trainer RAG features."""

from fastapi import HTTPException
from sqlalchemy.orm import Session
from uuid import UUID

from app.models.formation import Session as TrainingSession
from app.models.rh import Formateur
from app.models.user import User


def is_trainer(user: User) -> bool:
    return getattr(user.role, "value", user.role) == "FORMATEUR"


def assigned_formation_codes(db: Session, user: User) -> set[str]:
    """Only codes on sessions assigned to this trainer's account."""
    if not is_trainer(user):
        return set()
    trainer = db.query(Formateur).filter(Formateur.user_id == user.id).first()
    if trainer is None:
        return set()
    rows = (
        db.query(TrainingSession.formation_code)
        .filter(
            TrainingSession.formateur_id == trainer.id,
            TrainingSession.formation_code.isnot(None),
            TrainingSession.formation_code != "",
        )
        .distinct()
        .all()
    )
    return {code for (code,) in rows if code}


def assigned_session_ids(db: Session, user: User) -> set[str]:
    """Session UUIDs assigned to the trainer account, never only a shared course code."""
    if not is_trainer(user):
        return set()
    trainer = db.query(Formateur).filter(Formateur.user_id == user.id).first()
    if trainer is None:
        return set()
    rows = db.query(TrainingSession.id).filter(TrainingSession.formateur_id == trainer.id).all()
    return {str(session_id) for (session_id,) in rows}


def get_accessible_session(db: Session, user: User, session_id: str | None) -> TrainingSession:
    if not session_id:
        raise HTTPException(status_code=422, detail="Sélectionnez la session de formation concernée.")
    try:
        session_uuid = UUID(str(session_id))
    except (ValueError, TypeError):
        raise HTTPException(status_code=422, detail="Identifiant de session invalide.")
    session = db.query(TrainingSession).filter(TrainingSession.id == session_uuid).first()
    if session is None:
        raise HTTPException(status_code=404, detail="Session de formation introuvable.")
    if is_trainer(user) and str(session.id) not in assigned_session_ids(db, user):
        raise HTTPException(status_code=403, detail="Cette session ne vous est pas affectée.")
    return session


def require_assigned_code(db: Session, user: User, formation_code: str | None) -> None:
    if not is_trainer(user):
        return
    if not formation_code:
        raise HTTPException(status_code=422, detail="Sélectionnez une formation à laquelle vous êtes affecté.")
    if formation_code not in assigned_formation_codes(db, user):
        raise HTTPException(status_code=403, detail="Cette formation ne fait pas partie de vos sessions affectées.")
