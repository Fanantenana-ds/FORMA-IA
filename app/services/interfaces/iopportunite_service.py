from abc import ABC, abstractmethod
from typing import Optional
from uuid import UUID

from app.models.opportunite import Opportunite
from app.schemas.opportunite import OpportuniteCreate, OpportuniteUpdate, OpportuniteAnalyseRequest, OpportuniteAnalyseResult

class IOpportuniteService(ABC):
    @abstractmethod
    def create(self, data: OpportuniteCreate) -> Opportunite:
        pass

    @abstractmethod
    def get_by_id(self, opportunite_id: UUID) -> Optional[Opportunite]:
        pass

    @abstractmethod
    def get_all(self) -> list[Opportunite]:
        pass

    @abstractmethod
    def delete(self, opportunite_id: UUID) -> bool:
        pass

    @abstractmethod
    def update(self, opportunite_id: UUID, data: OpportuniteUpdate) -> Optional[Opportunite]:
        pass