from abc import ABC, abstractmethod
from app.schemas.opportunite import OpportuniteAnalyseResult

class IOpportuniteAnalyseService(ABC):
    @abstractmethod
    def analyse(self, contenu: str) -> OpportuniteAnalyseResult:
        pass
