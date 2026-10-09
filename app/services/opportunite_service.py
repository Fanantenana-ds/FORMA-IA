from uuid import UUID

from app.models.opportunite import Domaine, Opportunite, StatutOpportunite
from app.repositories.interfaces.iopportunite_repository import IOpportuniteRepository
from app.schemas.opportunite import OpportuniteCreate, OpportuniteUpdate
from app.services.interfaces.iopportunite_service import IOpportuniteService
from typing import List, Optional


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

    def get_by_id(self, opportunite_id: UUID) -> Opportunite | None:

        return self.repository.find_by_id(opportunite_id)

    def get_all(
        self,
        statut: Optional[StatutOpportunite] = None,
        domaine: Optional[Domaine] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> List[Opportunite]:
        return self.repository.find_all(statut=statut, domaine=domaine, skip=skip, limit=limit)

    def delete(self, opportunite_id: UUID) -> bool:
        return self.repository.delete(opportunite_id)

    def update(self, opportunite_id: UUID, data: OpportuniteUpdate) -> Opportunite | None:
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