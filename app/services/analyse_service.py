from uuid import UUID
from sqlalchemy.orm import Session
from app.models.opportunite import Opportunite, StatutOpportunite
from app.models.historique_analyse import HistoriqueAnalyse

class AnalyseService:
    def __init__(self, db: Session):
        self.db = db

    def analyser(self, opportunite: Opportunite, resultat_ia: dict, user_id: UUID) -> Opportunite:
        historique_analyse = HistoriqueAnalyse(
            opportunite_id=opportunite.id,
            user_id=user_id,
            objet=resultat_ia.get("objet"),
            budget=resultat_ia.get("budget"),
            echeance=resultat_ia.get("echeance"),
            domaine=resultat_ia.get("domaine"),
            score_pertinente=resultat_ia.get(
                "score_pertinente",
                0.0
            )
        )
        self.db.add(historique_analyse)
        opportunite.statut = StatutOpportunite.ANALYSEE

        self.db.commit()
        self.db.refresh(opportunite)

        return opportunite