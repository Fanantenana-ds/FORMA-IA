from sqlalchemy.orm import Session
from sqlalchemy import func

from app.models.formation import Session as FormationSession, Presence, StatutPresence
from app.models.opportunite import Opportunite
from app.schemas.dashboard import StatistiquesResponse


class DashboardService:
    def __init__(self, db: Session):
        self.db = db

    def obtenir_statistiques(self) -> StatistiquesResponse:
        session_realisees = self.db.query(FormationSession).count()

        participant = (
            self.db.query(Presence.participant_id)
            .distinct()
            .count()
        )

        total_presences = self.db.query(Presence).count()
        presences_effectives = (
            self.db.query(Presence)
            .filter(Presence.statut == StatutPresence.PRESENT)
            .count()
        )
        taux_presence = (
            round(presences_effectives / total_presences * 100, 2)
            if total_presences > 0 else 0.0
        )

        resultats_domaine = (
            self.db.query(Opportunite.domaine, func.count(Opportunite.id))
            .filter(Opportunite.domaine.isnot(None))
            .group_by(Opportunite.domaine)
            .all()
        )
        opportunite_par_domaine = {
            domaine.value: total for domaine, total in resultats_domaine
        }

        return StatistiquesResponse(
            session_realisees=session_realisees,
            participant=participant,
            taux_presence=taux_presence,
            opportunite_par_domaine=opportunite_par_domaine,
            chiffre_affaires_facture=0.0,
            chiffre_affaires_encaisse=0.0
        )