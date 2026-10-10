# app/services/projet_service.py
from typing import List, Optional
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.projet import BudgetFormation, EdtSession, Projet, Salle, StatutProjet
from app.schemas.projet import (
    BudgetCreate,
    EdtSessionCreate,
    ProjetCreate,
    ProjetReplace,
    ProjetUpdate,
    SalleCreate,
    SalleReplace,
    SalleUpdate,
)


class SalleService:
    def __init__(self, db: Session):
        self.db = db

    def creer(self, data: SalleCreate) -> Salle:
        salle = Salle(**data.model_dump())
        self.db.add(salle)
        self.db.commit()
        self.db.refresh(salle)
        return salle

    def get(self, salle_id: UUID) -> Salle:
        salle = self.db.query(Salle).filter(Salle.id == salle_id).first()
        if not salle:
            raise HTTPException(status_code=404, detail="Salle introuvable")
        return salle

    def lister(self, disponible: Optional[bool] = None, skip: int = 0, limit: int = 100) -> list[Salle]:
        q = self.db.query(Salle)
        if disponible is not None:
            q = q.filter(Salle.disponible == disponible)
        return q.order_by(Salle.nom).offset(skip).limit(limit).all()

    def mettre_a_jour(self, salle_id: UUID, data: SalleUpdate) -> Salle:
        salle = self.get(salle_id)
        for field, value in data.model_dump(exclude_none=True).items():
            setattr(salle, field, value)
        self.db.commit()
        self.db.refresh(salle)
        return salle

    def remplacer(self, salle_id: UUID, data: SalleReplace) -> Salle:
        salle = self.get(salle_id)
        for field, value in data.model_dump().items():
            setattr(salle, field, value)
        self.db.commit()
        self.db.refresh(salle)
        return salle

    def supprimer(self, salle_id: UUID) -> None:
        salle = self.get(salle_id)
        self.db.delete(salle)
        self.db.commit()


class ProjetService:
    def __init__(self, db: Session):
        self.db = db

    def _get_projet(self, projet_id: UUID) -> Projet:
        p = self.db.query(Projet).filter(Projet.id == projet_id).first()
        if not p:
            raise HTTPException(status_code=404, detail="Projet introuvable")
        return p

    def creer(self, data: ProjetCreate) -> Projet:
        projet = Projet(**data.model_dump())
        self.db.add(projet)
        self.db.commit()
        self.db.refresh(projet)
        return projet

    def get(self, projet_id: UUID) -> Projet:
        return self._get_projet(projet_id)

    def lister(
        self,
        statut: Optional[StatutProjet] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> list[Projet]:
        q = self.db.query(Projet)
        if statut:
            q = q.filter(Projet.statut == statut)
        return q.order_by(Projet.date_creation.desc()).offset(skip).limit(limit).all()

    def mettre_a_jour(self, projet_id: UUID, data: ProjetUpdate) -> Projet:
        projet = self._get_projet(projet_id)
        for field, value in data.model_dump(exclude_none=True).items():
            setattr(projet, field, value)
        self.db.commit()
        self.db.refresh(projet)
        return projet

    def remplacer(self, projet_id: UUID, data: ProjetReplace) -> Projet:
        projet = self._get_projet(projet_id)
        for field, value in data.model_dump().items():
            setattr(projet, field, value)
        self.db.commit()
        self.db.refresh(projet)
        return projet

    def supprimer(self, projet_id: UUID) -> None:
        projet = self._get_projet(projet_id)
        self.db.delete(projet)
        self.db.commit()

    # ── EDT ─────────────────────────────────────────────────

    def ajouter_edt(self, projet_id: UUID, data: EdtSessionCreate) -> EdtSession:
        self._get_projet(projet_id)
        edt = EdtSession(projet_id=projet_id, **data.model_dump())
        self.db.add(edt)
        self.db.commit()
        self.db.refresh(edt)
        return edt

    def lister_edt(self, projet_id: UUID) -> list[EdtSession]:
        self._get_projet(projet_id)
        return (
            self.db.query(EdtSession)
            .filter(EdtSession.projet_id == projet_id)
            .order_by(EdtSession.date, EdtSession.heure_debut)
            .all()
        )

    def supprimer_edt(self, projet_id: UUID, edt_id: UUID) -> None:
        self._get_projet(projet_id)
        edt = self.db.query(EdtSession).filter(
            EdtSession.id == edt_id, EdtSession.projet_id == projet_id
        ).first()
        if not edt:
            raise HTTPException(status_code=404, detail="Séance EDT introuvable")
        self.db.delete(edt)
        self.db.commit()

    # ── Budget ──────────────────────────────────────────────

    def creer_ou_maj_budget(self, projet_id: UUID, data: BudgetCreate, valideur_id: Optional[UUID] = None) -> BudgetFormation:
        self._get_projet(projet_id)
        cout_total = round(data.cout_formateur + data.cout_salle + data.cout_supports, 2)

        budget = self.db.query(BudgetFormation).filter(BudgetFormation.projet_id == projet_id).first()
        if budget:
            budget.cout_formateur = data.cout_formateur
            budget.cout_salle = data.cout_salle
            budget.cout_supports = data.cout_supports
            budget.cout_total = cout_total
            budget.valide = data.valide
            if data.valide and valideur_id:
                budget.valide_par = valideur_id
        else:
            budget = BudgetFormation(
                projet_id=projet_id,
                cout_formateur=data.cout_formateur,
                cout_salle=data.cout_salle,
                cout_supports=data.cout_supports,
                cout_total=cout_total,
                valide=data.valide,
                valide_par=valideur_id if data.valide else None,
            )
            self.db.add(budget)

        self.db.commit()
        self.db.refresh(budget)
        return budget

    def get_budget(self, projet_id: UUID) -> BudgetFormation:
        self._get_projet(projet_id)
        budget = self.db.query(BudgetFormation).filter(BudgetFormation.projet_id == projet_id).first()
        if not budget:
            raise HTTPException(status_code=404, detail="Aucun budget défini pour ce projet")
        return budget
