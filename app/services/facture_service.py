from datetime import date as date_type
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.facture import Facture, Paiement, StatutFacture
from app.schemas.facture import FactureCreate, PaiementCreate


class FactureService:
    def __init__(self, db: Session):
        self.db = db

    def _generer_numero(self) -> str:
        annee = date_type.today().year
        total = self.db.query(Facture).count()
        return f"FACT-{annee}-{total + 1:04d}"

    def emettre_facture(self, data: FactureCreate) -> Facture:
        facture = Facture(
            numero = self._generer_numero(),
            client = data.client,
            montant = data.montant,
            tva_taux = data.tva_taux,
            date_echeance = data.date_echeance,
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

        paiement = Paiement(facture_id=facture_id, **data.model_dump())
        self.db.add(paiement)
        self.db.flush()

        total_paye = sum(p.montant for p in facture.paiements) + data.montant
        if total_paye >= facture.montant_ttc:
            facture.statut = StatutFacture.PAYEE
        elif total_paye > 0:
            facture.statut = StatutFacture.PARTIELLEMENT_PAYEE

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

    def lister(self):
        return self.db.query(Facture).all()