from typing import Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.opportunite import Opportunite
from app.repositories.interfaces.iopportunite_repository import IOpportuniteRepository

class OpportuniteRepository(IOpportuniteRepository):
    def __init__(self, db: Session):
        self.db = db

    def save(self, opportunite: Opportunite) -> Opportunite:
        self.db.add(opportunite)
        self.db.commit()
        self.db.refresh(opportunite)

        return opportunite

    def find_by_id(self, opportunite_id: UUID) -> Optional[Opportunite]:
        return (
            self.db.query(Opportunite)
            .filter(Opportunite.id == opportunite_id)
            .first()
        )

    def find_all(self) -> list[Opportunite]:
        return (
            self.db.query(Opportunite)
            .order_by(Opportunite.date_creation.desc())
            .all()
        )

    def delete(self, opportunite_id: UUID) -> bool:
        opportunite = self.find_by_id(opportunite_id)

        if not opportunite:
            return False

        self.db.delete(opportunite)
        self.db.commit()

        return True

    def update(self, opportunite: Opportunite) -> Opportunite:
        self.db.merge(opportunite)
        self.db.commit()
        self.db.refresh(opportunite)

        return opportunite