from uuid import UUID
from typing import List, Optional

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.rh import Formateur, Candidat, Entretien
from app.schemas.rh import (
    FormateurCreate, FormateurUpdate,
    CandidatCreate, CandidatUpdate,
    EntretienCreate, EntretienUpdate,
)


class RhService:
    def __init__(self, db: Session):
        self.db = db

    # =========================================================================
    # FORMATEURS
    # =========================================================================

    def creer_formateur(self, data: FormateurCreate) -> Formateur:
        formateur = Formateur(**data.model_dump())
        self.db.add(formateur)
        self.db.commit()
        self.db.refresh(formateur)
        return formateur

    def get_formateur(self, formateur_id: UUID) -> Formateur:
        f = self.db.query(Formateur).filter(Formateur.id == formateur_id).first()
        if not f:
            raise HTTPException(status_code=404, detail="Formateur introuvable")
        return f

    def lister_formateurs(
        self,
        specialite: Optional[str] = None,
        statut: Optional[str] = None,
    ) -> List[Formateur]:
        q = self.db.query(Formateur)
        if specialite:
            q = q.filter(Formateur.specialite.ilike(f"%{specialite}%"))
        if statut:
            q = q.filter(Formateur.statut == statut)
        return q.order_by(Formateur.nom).all()

    def mettre_a_jour_formateur(
        self, formateur_id: UUID, data: FormateurUpdate
    ) -> Formateur:
        f = self.get_formateur(formateur_id)
        for field, value in data.model_dump(exclude_none=True).items():
            setattr(f, field, value)
        self.db.commit()
        self.db.refresh(f)
        return f

    def supprimer_formateur(self, formateur_id: UUID) -> None:
        f = self.get_formateur(formateur_id)
        self.db.delete(f)
        self.db.commit()

    # =========================================================================
    # CANDIDATS
    # =========================================================================

    def creer_candidat(self, data: CandidatCreate) -> Candidat:
        candidat = Candidat(**data.model_dump())
        self.db.add(candidat)
        self.db.commit()
        self.db.refresh(candidat)
        return candidat

    def get_candidat(self, candidat_id: UUID) -> Candidat:
        c = self.db.query(Candidat).filter(Candidat.id == candidat_id).first()
        if not c:
            raise HTTPException(status_code=404, detail="Candidat introuvable")
        return c

    def lister_candidats(
        self,
        poste_vise: Optional[str] = None,
        decision: Optional[str] = None,
    ) -> List[Candidat]:
        q = self.db.query(Candidat)
        if poste_vise:
            q = q.filter(Candidat.poste_vise.ilike(f"%{poste_vise}%"))
        if decision:
            q = q.filter(Candidat.decision_preselection == decision)
        return q.order_by(Candidat.date_creation.desc()).all()

    def mettre_a_jour_candidat(
        self, candidat_id: UUID, data: CandidatUpdate
    ) -> Candidat:
        c = self.get_candidat(candidat_id)
        for field, value in data.model_dump(exclude_none=True).items():
            setattr(c, field, value)
        self.db.commit()
        self.db.refresh(c)
        return c

    def supprimer_candidat(self, candidat_id: UUID) -> None:
        c = self.get_candidat(candidat_id)
        self.db.delete(c)
        self.db.commit()

    # =========================================================================
    # ENTRETIENS
    # =========================================================================

    def creer_entretien(self, candidat_id: UUID, data: EntretienCreate) -> Entretien:
        self.get_candidat(candidat_id)   # lève 404 si absent
        entretien = Entretien(candidat_id=candidat_id, **data.model_dump())
        self.db.add(entretien)
        self.db.commit()
        self.db.refresh(entretien)
        return entretien

    def get_entretien(self, entretien_id: UUID) -> Entretien:
        e = self.db.query(Entretien).filter(Entretien.id == entretien_id).first()
        if not e:
            raise HTTPException(status_code=404, detail="Entretien introuvable")
        return e

    def lister_entretiens(self, candidat_id: UUID) -> List[Entretien]:
        self.get_candidat(candidat_id)
        return (
            self.db.query(Entretien)
            .filter(Entretien.candidat_id == candidat_id)
            .order_by(Entretien.date_creation.desc())
            .all()
        )

    def mettre_a_jour_entretien(
        self, entretien_id: UUID, data: EntretienUpdate
    ) -> Entretien:
        e = self.get_entretien(entretien_id)
        for field, value in data.model_dump(exclude_none=True).items():
            setattr(e, field, value)
        self.db.commit()
        self.db.refresh(e)
        return e

    def supprimer_entretien(self, entretien_id: UUID) -> None:
        e = self.get_entretien(entretien_id)
        self.db.delete(e)
        self.db.commit()
