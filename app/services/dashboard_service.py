from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.facture import Facture, Paiement
from app.models.formation import Presence, StatutPresence
from app.models.formation import Session as FormationSession
from app.models.opportunite import Opportunite
from app.schemas.dashboard import StatistiquesResponse


class DashboardService:
    def __init__(self, db: Session):
        self.db = db

    def obtenir_statistiques(self) -> StatistiquesResponse:
        # ----------------------------------------------------------------
        # FORMATIONS
        # ----------------------------------------------------------------
        session_realisees = self.db.query(FormationSession).count()

        participant = (
            self.db.query(Presence.participant_id)
            .distinct()
            .count()
        )

        total_presences = self.db.query(Presence).count()
        presences_effectives = (
            self.db.query(Presence)
            .filter(Presence.statut == StatutPresence.PRESENT)
            .count()
        )
        taux_presence = (
            round(presences_effectives / total_presences * 100, 2)
            if total_presences > 0 else 0.0
        )

        # ----------------------------------------------------------------
        # OPPORTUNITÉS
        # ----------------------------------------------------------------
        opportunite_total = self.db.query(Opportunite).count()

        resultats_domaine = (
            self.db.query(Opportunite.domaine, func.count(Opportunite.id))
            .filter(Opportunite.domaine.isnot(None))
            .group_by(Opportunite.domaine)
            .all()
        )
        opportunite_par_domaine = {
            domaine.value: total for domaine, total in resultats_domaine
        }

        resultats_statut = (
            self.db.query(Opportunite.statut, func.count(Opportunite.id))
            .group_by(Opportunite.statut)
            .all()
        )
        opportunite_par_statut = {
            statut.value: total for statut, total in resultats_statut
        }

        # ----------------------------------------------------------------
        # DOCUMENTS GÉNÉRÉS
        # ----------------------------------------------------------------
        tdr_generes = (
            self.db.query(Document)
            .filter(Document.type == TypeDocument.TDR)
            .count()
        )
        offres_generees = (
            self.db.query(Document)
            .filter(Document.type == TypeDocument.OFFRE)
            .count()
        )
        attestations_generees = (
            self.db.query(Document)
            .filter(Document.type == TypeDocument.ATTESTATION)
            .count()
        )

        # ----------------------------------------------------------------
        # FACTURATION
        # ----------------------------------------------------------------
        chiffre_affaires_facture = (
            self.db.query(func.sum(Facture.montant))
            .scalar() or 0.0
        )

        chiffre_affaires_encaisse = (
            self.db.query(func.sum(Paiement.montant))
            .scalar() or 0.0
        )

        factures_en_retard = (
            self.db.query(Facture)
            .filter(Facture.statut == StatutFacture.EN_RETARD)
            .count()
        )

        # Montant impayé = somme TTC des factures non soldées - somme des paiements reçus
        factures_non_soldees = (
            self.db.query(Facture)
            .filter(Facture.statut != StatutFacture.PAYEE)
            .all()
        )

        montant_impaye = 0.0
        for facture in factures_non_soldees:
            total_paye = sum(p.montant for p in facture.paiements)
            reste = facture.montant_ttc - total_paye
            if reste > 0:
                montant_impaye += reste

        montant_impaye = round(montant_impaye, 2)

        relances_envoyees = self.db.query(Relance).count()

        return StatistiquesResponse(
            session_realisees=session_realisees,
            participant=participant,
            taux_presence=taux_presence,
            opportunite_total=opportunite_total,
            opportunite_par_domaine=opportunite_par_domaine,
            opportunite_par_statut=opportunite_par_statut,
            tdr_generes=tdr_generes,
            offres_generees=offres_generees,
            attestations_generees=attestations_generees,
            chiffre_affaires_facture=round(chiffre_affaires_facture, 2),
            chiffre_affaires_encaisse=round(chiffre_affaires_encaisse, 2),
            factures_en_retard=factures_en_retard,
            montant_impaye=montant_impaye,
            relances_envoyees=relances_envoyees,
        )
