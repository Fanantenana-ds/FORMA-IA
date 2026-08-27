from app.schemas.opportunite import OpportuniteAnalyseResult
from app.services.interfaces.iopportunite_analyse_service import IOpportuniteAnalyseService

class OpportuniteAnalyseService(IOpportuniteAnalyseService):
    def analyse(self, contenu: str) -> OpportuniteAnalyseResult:
        """
        Test analyse opportunité backend sans intégration IA
        """

        return OpportuniteAnalyseResult(
            objet="Analyse temporaire",
            budget=None,
            echeance=None,
            domaine=None,
            score_pertinence=0.0
        )
