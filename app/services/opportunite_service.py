from typing import Optional
from uuid import UUID

from app.models.opportunite import Opportunite
from app.schemas.opportunite import OpportuniteCreate, OpportuniteUpdate
from app.repositories.interfaces.iopportunite_repository import IOpportuniteRepository
from app.services.interfaces.iopportunite_service import IOpportuniteService

class OpportuniteService(IOpportuniteService):
    def __init__(self, repository: IOpportuniteRepository):
        self.repository = repository

    def create(self, data: OpportuniteCreate) -> Opportunite:
        opportunite = Opportunite(
            source=data.source,
            contenu=data.contenu,
            objet=data.objet,
            budget=data.budget,
            echeance=data.echeance,
            domaine=data.domaine
        )

        return self.repository.save(opportunite)

    def get_by_id(self, opportunite_id: UUID) -> Optional[Opportunite]:

        return self.repository.find_by_id(opportunite_id)

    def get_all(self) -> list[Opportunite]:

        return self.repository.find_all()

    def delete(self, opportunite_id: UUID) -> bool:
        return self.repository.delete(opportunite_id)

    def update(self, opportunite_id: UUID, data: OpportuniteUpdate) -> Optional[Opportunite]:
        opportunite = self.repository.find_by_id(opportunite_id)

        if not opportunite:
            return None

        opportunite.source = data.source
        opportunite.contenu = data.contenu
        opportunite.objet = data.objet
        opportunite.budget = data.budget
        opportunite.echeance = data.echeance
        opportunite.domaine = data.domaine

        return self.repository.update(opportunite)