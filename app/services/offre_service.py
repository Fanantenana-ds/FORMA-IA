# app/services/offre_service.py
from typing import List, Optional
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.offre import Offre, StatutOffre
from app.schemas.offre import OffreCreate, OffreReplace, OffreUpdate


class OffreService:
    def __init__(self, db: Session):
        self.db = db

    def creer(self, data: OffreCreate) -> Offre:
        offre = Offre(**data.model_dump())
        self.db.add(offre)
        self.db.commit()
        self.db.refresh(offre)
        return offre

    def get(self, offre_id: UUID) -> Offre:
        offre = self.db.query(Offre).filter(Offre.id == offre_id).first()
        if not offre:
            raise HTTPException(status_code=404, detail="Offre introuvable")
        return offre

    def lister(
        self,
        statut: Optional[StatutOffre] = None,
        client: Optional[str] = None,
        opportunite_id: Optional[UUID] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> list[Offre]:
        q = self.db.query(Offre)
        if statut:
            q = q.filter(Offre.statut == statut)
        if client:
            q = q.filter(Offre.client.ilike(f"%{client}%"))
        if opportunite_id:
            q = q.filter(Offre.opportunite_id == opportunite_id)
        return q.order_by(Offre.date_creation.desc()).offset(skip).limit(limit).all()

    def mettre_a_jour(self, offre_id: UUID, data: OffreUpdate) -> Offre:
        offre = self.get(offre_id)
        for field, value in data.model_dump(exclude_none=True).items():
            setattr(offre, field, value)
        self.db.commit()
        self.db.refresh(offre)
        return offre

    def remplacer(self, offre_id: UUID, data: OffreReplace) -> Offre:
        """PUT — remplacement complet : tous les champs sont écrasés."""
        offre = self.get(offre_id)
        for field, value in data.model_dump().items():
            setattr(offre, field, value)
        self.db.commit()
        self.db.refresh(offre)
        return offre

    def supprimer(self, offre_id: UUID) -> None:
        offre = self.get(offre_id)
        self.db.delete(offre)
        self.db.commit()
