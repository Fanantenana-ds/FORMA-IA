from datetime import date as date_type
from typing import List, Optional
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.facture import Facture, Paiement, Relance, StatutFacture
from app.models.formation import Session as TrainingSession
from app.schemas.facture import FactureCreate, FactureUpdate, PaiementCreate, RelanceIACreate


class FactureService:
    def __init__(self, db: Session):
        self.db = db

    def _generer_numero(self) -> str:
        annee = date_type.today().year
        total = self.db.query(Facture).count()
        return f"FACT-{annee}-{total + 1:04d}"

    def emettre_facture(self, data: FactureCreate) -> Facture:
        session = None
        if data.session_id:
            session = self.db.query(TrainingSession).filter(TrainingSession.id == data.session_id).first()
            if not session:
                raise HTTPException(status_code=404, detail="Session introuvable.")
            if session.date_fin > date_type.today():
                raise HTTPException(status_code=422, detail="Une facture depuis une session ne peut être créée qu’après sa date de fin.")
        client = (data.client or (session.client if session else None) or "").strip()
        if not client:
            raise HTTPException(status_code=422, detail="Le client est obligatoire pour émettre la facture.")
        facture = Facture(
            numero = self._generer_numero(),
            client = client,
            client_adresse = data.client_adresse,
            client_siret = data.client_siret,
            client_rcs = data.client_rcs,
            client_tva = data.client_tva,
            montant = data.montant,
            tva_taux = data.tva_taux,
            date_echeance = data.date_echeance,
            session_id = data.session_id,
            statut = StatutFacture.EMISE
        )
        self.db.add(facture)
        self.db.commit()
        self.db.refresh(facture)
        return facture

    def get_facture(self, facture_id: UUID) -> Facture:
        facture = self.db.query(Facture).filter(Facture.id == facture_id).first()
        if not facture:
            raise HTTPException(status_code=404, detail="Facture introuvable")
        return facture

    def ajouter_paiement(self, facture_id: UUID, data: PaiementCreate) -> Facture:
        facture = self.get_facture(facture_id)

        if facture.statut == StatutFacture.ANNULEE:
            raise HTTPException(status_code=409, detail="Impossible d'enregistrer un paiement sur une facture annulée.")

        total_paye = sum(p.montant for p in facture.paiements)
        restant_du = round(facture.montant_ttc - total_paye, 2)
        if data.montant > restant_du:
            raise HTTPException(
                status_code=422,
                detail=f"Le paiement dépasse le montant restant dû ({restant_du:.2f}).",
            )

        paiement = Paiement(facture_id=facture_id, **data.model_dump())
        self.db.add(paiement)
        total_paye += data.montant
        if total_paye >= facture.montant_ttc:
            facture.statut = StatutFacture.PAYEE
        elif total_paye > 0:
            facture.statut = StatutFacture.PARTIELLEMENT_PAYEE

        self.db.commit()
        self.db.refresh(facture)
        return facture

    def mettre_a_jour_facture(self, facture_id: UUID, data: FactureUpdate) -> Facture:
        """Mise à jour partielle d'une facture (PATCH semantics)."""
        facture = self.get_facture(facture_id)
        for field, value in data.model_dump(exclude_none=True).items():
            setattr(facture, field, value)
        self.db.commit()
        self.db.refresh(facture)
        return facture

    def verifier_retard(self, facture_id: UUID) -> Facture:
        facture = self.get_facture(facture_id)
        if (
            facture.statut not in (StatutFacture.PAYEE,)
            and facture.date_echeance
            and facture.date_echeance < date_type.today()
        ):
            facture.statut = StatutFacture.EN_RETARD
            self.db.commit()
            self.db.refresh(facture)
        return facture

    def generer_relance(self, facture_id: UUID) -> str:
        facture = self.verifier_retard(facture_id)
        reste = round(facture.montant_ttc - sum(p.montant for p in facture.paiements), 2)
        return (
            f"Relance - Facture {facture.numero}\n"
            f"Client : {facture.client}\n"
            f"Montant restant dû : {reste} Ar\n"
            f"Échéance dépassée le : {facture.date_echeance}\n"
            f"Merci de bien vouloir régulariser cette facture dans les meilleurs délais."
        )

    def enregistrer_relance_ia(self, facture_id: UUID, data: RelanceIACreate) -> Relance:
        """Persiste une relance IA approuvée (HITL) liée à une facture."""
        self.get_facture(facture_id)  # lève 404 si introuvable
        relance = Relance(
            facture_id=facture_id,
            niveau=data.niveau,
            objet=data.objet,
            texte=data.texte,
            review_id=data.review_id,
        )
        self.db.add(relance)
        self.db.commit()
        self.db.refresh(relance)
        return relance

    def lister_relances(self, facture_id: UUID):
        self.get_facture(facture_id)
        return self.db.query(Relance).filter(Relance.facture_id == facture_id).all()

    def supprimer_facture(self, facture_id: UUID) -> None:
        """Supprime une facture et ses paiements/relances (cascade ORM)."""
        facture = self.get_facture(facture_id)
        self.db.delete(facture)
        self.db.commit()

    def lister(
        self,
        statut: StatutFacture | None = None,
        client: str | None = None,
        skip: int = 0,
        limit: int = 100,
    ) -> list[Facture]:
        q = self.db.query(Facture)
        if statut is not None:
            q = q.filter(Facture.statut == statut)
        if client is not None:
            q = q.filter(Facture.client.ilike(f"%{client}%"))
        factures = q.order_by(Facture.date_emission.desc()).offset(skip).limit(limit).all()
        today = date_type.today()
        changed = False
        for facture in factures:
            if facture.statut not in (StatutFacture.PAYEE, StatutFacture.ANNULEE) and facture.date_echeance and facture.date_echeance < today:
                paid = sum(payment.montant for payment in facture.paiements)
                if paid < facture.montant_ttc and facture.statut != StatutFacture.EN_RETARD:
                    facture.statut = StatutFacture.EN_RETARD
                    changed = True
        if changed:
            self.db.commit()
        return factures
