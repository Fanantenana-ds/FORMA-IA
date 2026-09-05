from uuid import UUID
from fastapi import HTTPException
from sqlalchemy.orm import Session as DbSession

from app.models.formation import Session, Seance, Participant, Presence
from app.schemas.formation import SessionCreate, SeanceCreate, ParticipantCreate, PresenceCreate

class FormationService:
    def __init__(self, db: DbSession):
        self.db = db

    def creer_session(self, data: SessionCreate) -> Session:
        session = Session(**data.model_dump())
        self.db.add(session)
        self.db.commit()
        self.db.refresh(session)
        return session

    def get_session(self, session_id: UUID) -> Session:
        session = self.db.query(Session).filter(Session.id == session_id).first()
        if not session:
            raise HTTPException(status_code=404, detail="Session introuvable")
        return session

    def ajouter_seance(self, session_id: UUID, data: SeanceCreate) -> Seance:
        self.get_session(session_id)
        seance = Seance(session_id=session_id, **data.model_dump())
        self.db.add(seance)
        self.db.commit()
        self.db.refresh(seance)
        return seance

    def creer_participant(self, data: ParticipantCreate) -> ParticipantCreate:
        participant = Participant(**data.model_dump())
        self.db.add(participant)
        self.db.commit()
        self.db.refresh(participant)
        return participant

    def enregistrer_presence(self, seance_id: UUID, data: PresenceCreate) -> PresenceCreate:
        seance = self.db.query(Seance).filter(Seance.id == seance_id).first()
        if not seance:
            raise HTTPException(status_code=404, detail="Séance introuvable")

        presence = Presence(seance_id=seance_id, **data.model_dump())
        self.db.add(presence)
        self.db.commit()
        self.db.refresh(presence)
        return presence