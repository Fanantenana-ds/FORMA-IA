from sqlalchemy.orm import Session
from sqlalchemy import func

from app.models.formation import Session as FormationSession, Presence, StatutPresence
from app.models.opportunite import Opportunite, StatutOpportunite
from app.schemas.dashboard import StatistiquesResponse


class DashboardService:
    def __init__(self, db: Session):
        self.db = db

    def obtenir_statistiques(self) -> StatistiquesResponse:
        session_realisees = self.db.query(FormationSession).count()

        participants_total = (
            self.db.query(Presence.participant_id)
            .distinct()
            .count()
        )

        total_presence = self.db.query(Presence).count()
        presence_effectives = (
            self.db.query(Presence)
            .filter(Presence.statut == StatutPresence.PRESENT)
            .count()
        )
        taux_presence = (
            round(presence_effectives / total_presence * 100, 2)
            if total_presence > 0 else 0.0
        )

        opportunites_total = self.db.query(Opportunite).count()
        opportunies_analysees = (
            self.db.query(Opportunite)
            .filter(Opportunite.statut == StatutOpportunite.ANALYSEE)
            .count()
        )

        return StatistiquesResponse(
            session_realisees=session_realisees,
            participant_total=participants_total,
            taux_presence=taux_presence,
            chiffre_affaire=0.0,
            opportunite_total=opportunites_total,
            opportunite_analysees=opportunies_analysees
        )