from abc import ABC, abstractmethod
from typing import Optional
from uuid import UUID

from app.models.opportunite import Opportunite
from app.schemas.opportunite import OpportuniteUpdate

class IOpportuniteRepository(ABC):
    @abstractmethod
    def save(self, opportunite: Opportunite) -> Opportunite:
        pass

    @abstractmethod
    def find_by_id(self, opportunite_id: UUID) -> Optional[Opportunite]:
        pass

    @abstractmethod
    def find_all(self) -> list[Opportunite]:
        pass

    @abstractmethod
    def delete(self, opportunite_id: UUID) -> bool:
        pass

    @abstractmethod
    def update(self, opportunite_id: UUID, data: OpportuniteUpdate) -> Optional[Opportunite]:
        pass