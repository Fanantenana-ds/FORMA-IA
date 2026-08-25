from sqlalchemy.orm import Session
from app.models.opportunite import Opportunite, StatutOpportunite

class AnalyseService:
    def __init__(self, db: Session):
        self.db = db

    def analyser(self, opportunite: Opportunite, resultat_ia: dict) -> Opportunite:
        opportunite.objet = resultat_ia.get("objet")
        opportunite.budget = resultat_ia.get("budget")
        opportunite.echeance = resultat_ia.get("ecehance")
        opportunite.domaine = resultat_ia.get("domaine")
        opportunite.score_pertinente = resultat_ia.get(
            "score_pertinente",
            0.0
        )
        opportunite.statut = StatutOpportunite.ANALYSEE

        self.db.commit()
        self.db.refresh(opportunite)

        return opportunite