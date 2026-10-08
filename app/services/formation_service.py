from typing import List, Optional
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy.orm import Session as DbSession
from datetime import date as date_type

from app.models.formation import Participant, Presence, Seance, Session
from app.schemas.formation import (
    ParticipantCreate,
    PresenceCreate,
    SeanceCreate,
    SessionCreate,
)


class FormationService:
    def __init__(self, db: DbSession):
        self.db = db

    def creer_session(self, data: SessionCreate) -> Session:
        valeurs = data.model_dump()
        # Session.date_fin est NOT NULL en base alors que le schéma la
        # déclare optionnelle : sans valeur, l'insertion échouait (HTTP 500).
        # Défaut : même jour que date_debut (aucune durée n'est supposée).
        valeurs["date_fin"] = valeurs["date_fin"] or valeurs["date_debut"]
        session = Session(**valeurs)
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
        valeurs = data.model_dump()
        # Seance.duree et Seance.theme sont NOT NULL en base alors que le
        # schéma les déclare optionnels : sans valeur, l'insertion échouait
        # (HTTP 500).
        valeurs["duree"] = valeurs["duree"] or "Non précisée"
        valeurs["theme"] = valeurs["theme"] or "Non précisé"
        seance = Seance(session_id=session_id, **valeurs)
        self.db.add(seance)
        self.db.commit()
        self.db.refresh(seance)
        return seance

    def creer_participant(self, data: ParticipantCreate) -> Participant:
        participant = Participant(**data.model_dump())
        self.db.add(participant)
        self.db.commit()
        self.db.refresh(participant)
        return participant

    def enregistrer_presence(self, seance_id: UUID, data: PresenceCreate) -> Presence:
        seance = self.db.query(Seance).filter(Seance.id == seance_id).first()
        if not seance:
            raise HTTPException(status_code=404, detail="Séance introuvable")

        presence = Presence(seance_id=seance_id, **data.model_dump())
        self.db.add(presence)
        self.db.commit()
        self.db.refresh(presence)
        return presence

    # -------------------------------------------------------------------------
    # LISTE DES SESSIONS
    # -------------------------------------------------------------------------

    def mettre_a_jour_session(self, session_id: UUID, data: SessionUpdate) -> Session:
        """Mise à jour partielle d'une session (PATCH semantics)."""
        session = self.get_session(session_id)
        for field, value in data.model_dump(exclude_none=True).items():
            setattr(session, field, value)
        # Cohérence : date_fin ne peut pas être avant date_debut
        if session.date_fin and session.date_debut and session.date_fin < session.date_debut:
            raise HTTPException(
                status_code=422,
                detail="date_fin ne peut pas être antérieure à date_debut.",
            )
        self.db.commit()
        self.db.refresh(session)
        return session

    def supprimer_session(self, session_id: UUID) -> None:
        """Supprime une session et toutes ses séances (cascade définie en DB)."""
        session = self.get_session(session_id)
        self.db.delete(session)
        self.db.commit()

    def lister_sessions(
        self,
        formateur_id: Optional[UUID] = None,
        client: Optional[str] = None,
        date_debut_min: Optional[date_type] = None,
        date_debut_max: Optional[date_type] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> List[FormationSession]:
        q = self.db.query(FormationSession)
        if formateur_id is not None:
            q = q.filter(FormationSession.formateur_id == formateur_id)
        if client:
            q = q.filter(FormationSession.client.ilike(f"%{client}%"))
        if date_debut_min is not None:
            q = q.filter(FormationSession.date_debut >= date_debut_min)
        if date_debut_max is not None:
            q = q.filter(FormationSession.date_debut <= date_debut_max)
        return (
            q.order_by(FormationSession.date_debut.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )
    # -------------------------------------------------------------------------
    # SÉANCES D'UNE SESSION
    # -------------------------------------------------------------------------

    def lister_seances(self, session_id: UUID) -> List[Seance]:
        self.get_session(session_id)   # lève 404 si absente
        return (
            self.db.query(Seance)
            .filter(Seance.session_id == session_id)
            .order_by(Seance.date)
            .all()
        )

    # -------------------------------------------------------------------------
    # PARTICIPANTS
    # -------------------------------------------------------------------------

    def get_participant(self, participant_id: UUID) -> Participant:
        p = self.db.query(Participant).filter(Participant.id == participant_id).first()
        if not p:
            raise HTTPException(status_code=404, detail="Participant introuvable")
        return p

    def lister_participants(
    self,
    nom: Optional[str] = None,
    skip: int = 0,
    limit: int = 100,
    ) -> List[Participant]:
        q = self.db.query(Participant)
        if nom:
            q = q.filter(Participant.nom.ilike(f"%{nom}%"))
        return q.order_by(Participant.nom).offset(skip).limit(limit).all()
    # -------------------------------------------------------------------------
    # INSCRIPTIONS — inscrire / désinscrire / lister
    # -------------------------------------------------------------------------

    def inscrire_participant(self, session_id: UUID, data: InscriptionCreate) -> Inscription:
        """Inscrit un participant existant à une session (clé unique session+participant)."""
        self.get_session(session_id)
        self.get_participant(data.participant_id)

        doublon = (
            self.db.query(Inscription)
            .filter(
                Inscription.session_id == session_id,
                Inscription.participant_id == data.participant_id,
            )
            .first()
        )
        if doublon:
            raise HTTPException(
                status_code=409,
                detail="Ce participant est déjà inscrit à cette session.",
            )

        inscription = Inscription(
            session_id=session_id,
            participant_id=data.participant_id,
        )
        self.db.add(inscription)
        self.db.commit()
        self.db.refresh(inscription)
        return inscription

    def desinscrire_participant(self, session_id: UUID, participant_id: UUID) -> None:
        """Supprime l'inscription d'un participant à une session."""
        self.get_session(session_id)
        inscription = (
            self.db.query(Inscription)
            .filter(
                Inscription.session_id == session_id,
                Inscription.participant_id == participant_id,
            )
            .first()
        )
        if not inscription:
            raise HTTPException(status_code=404, detail="Inscription introuvable")
        self.db.delete(inscription)
        self.db.commit()

    # -------------------------------------------------------------------------
    # SÉANCES — PATCH / DELETE + lister présences
    # -------------------------------------------------------------------------

    def get_seance(self, seance_id: UUID) -> Seance:
        seance = self.db.query(Seance).filter(Seance.id == seance_id).first()
        if not seance:
            raise HTTPException(status_code=404, detail="Séance introuvable")
        return seance

    def mettre_a_jour_seance(self, seance_id: UUID, data: SeanceUpdate) -> Seance:
        """Mise à jour partielle d'une séance (PATCH semantics)."""
        seance = self.get_seance(seance_id)
        for field, value in data.model_dump(exclude_none=True).items():
            setattr(seance, field, value)
        self.db.commit()
        self.db.refresh(seance)
        return seance

    def supprimer_seance(self, seance_id: UUID) -> None:
        """Supprime une séance et toutes ses présences (cascade)."""
        seance = self.get_seance(seance_id)
        self.db.delete(seance)
        self.db.commit()

    # -------------------------------------------------------------------------
    # PRÉSENCES — lister + corriger
    # -------------------------------------------------------------------------

    def lister_presences(self, seance_id: UUID) -> List[Presence]:
        self.get_seance(seance_id)
        return (
            self.db.query(Presence)
            .filter(Presence.seance_id == seance_id)
            .all()
        )

    def get_presence(self, presence_id: UUID) -> Presence:
        presence = self.db.query(Presence).filter(Presence.id == presence_id).first()
        if not presence:
            raise HTTPException(status_code=404, detail="Présence introuvable")
        return presence

    def mettre_a_jour_presence(self, presence_id: UUID, data: PresenceUpdate) -> Presence:
        """Corrige le statut d'une présence (PATCH semantics)."""
        presence = self.get_presence(presence_id)
        presence.statut = data.statut
        self.db.commit()
        self.db.refresh(presence)
        return presence

    # -------------------------------------------------------------------------
    # PARTICIPANTS — PATCH / DELETE
    # -------------------------------------------------------------------------

    def mettre_a_jour_participant(self, participant_id: UUID, data: ParticipantUpdate) -> Participant:
        """Mise à jour partielle d'un participant (PATCH semantics)."""
        participant = self.get_participant(participant_id)
        for field, value in data.model_dump(exclude_none=True).items():
            setattr(participant, field, value)
        self.db.commit()
        self.db.refresh(participant)
        return participant

    def supprimer_participant(self, participant_id: UUID) -> None:
        """Supprime un participant (et ses présences/inscriptions via cascade DB)."""
        participant = self.get_participant(participant_id)
        self.db.delete(participant)
        self.db.commit()

    def lister_participants_session(self, session_id: UUID) -> List[Participant]:
        """Retourne les participants inscrits à une session (via la table inscriptions)."""
        self.get_session(session_id)
        inscriptions = (
            self.db.query(Inscription)
            .filter(Inscription.session_id == session_id)
            .all()
        )
        participant_ids = [i.participant_id for i in inscriptions]
        if not participant_ids:
            return []
        return (
            self.db.query(Participant)
            .filter(Participant.id.in_(participant_ids))
            .order_by(Participant.nom)
            .all()
        )