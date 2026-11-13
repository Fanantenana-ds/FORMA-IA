"""État d'un dossier de formation : toutes les étapes M1→M7 calculées côté serveur."""
from uuid import UUID

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.document import Document, StatutValidation, TypeDocument
from app.models.facture import Facture, Paiement
from app.models.formation import Inscription, Seance
from app.models.formation import Session as FormationSession
from app.models.offre import Offre
from app.models.opportunite import Opportunite
from app.models.projet import BudgetFormation, EdtSession, Projet
from app.services.rag import registry_service as registre

# Étape → module de navigation du frontend où l'utilisateur agit.
CIBLES = {
    "opportunite": "veille_marche",
    "tdr": "opportunites_crm",
    "offre_technique": "opportunites_crm",
    "offre_financiere": "opportunites_crm",
    "preparation": "dossiers_formation",
    "formateur": "sessions_groupes",
    "session": "sessions_groupes",
    "participants": "sessions_groupes",
    "supports": "espace_ia",
    "seances": "sessions_groupes",
    "attestations": "sessions_groupes",
    "facturation": "facturation_devis",
}


def _etape(cle: str, titre: str, etat: str, detail: str) -> dict:
    return {"cle": cle, "titre": titre, "etat": etat, "detail": detail, "cible": CIBLES[cle]}


class DossierService:
    def __init__(self, db: Session):
        self.db = db

    def obtenir_etat(self, opportunite_id: UUID) -> dict | None:
        opp = self.db.query(Opportunite).filter(Opportunite.id == opportunite_id).first()
        if opp is None:
            return None

        db = self.db
        tdrs = db.query(Document).filter(
            Document.opportunite_id == opp.id, Document.type == TypeDocument.TDR
        ).all()
        offres = db.query(Offre).filter(Offre.opportunite_id == opp.id).all()
        projet = (
            db.query(Projet).filter(Projet.opportunite_id == opp.id)
            .order_by(Projet.date_creation.desc()).first()
        )
        sessions = (
            db.query(FormationSession).filter(FormationSession.opportunite_id == opp.id)
            .order_by(FormationSession.date_creation.desc()).all()
        )
        session = sessions[0] if sessions else None

        etapes = [
            _etape("opportunite", "Opportunité identifiée", "done",
                   f"{opp.objet or 'Opportunité'} · statut {opp.statut.value}"),
            self._tdr(tdrs),
            self._offre(offres, "trame_technique", "offre_technique", "Offre technique"),
            self._offre(offres, "trame_financiere", "offre_financiere", "Offre financière"),
            self._preparation(projet, bool(offres)),
            *self._session_etapes(session),
        ]

        prochaine = next((e for e in etapes if e["etat"] in ("pending", "warning")), None)
        faites = sum(1 for e in etapes if e["etat"] == "done")
        return {
            "opportunite_id": str(opp.id),
            "titre": opp.objet,
            "statut_opportunite": opp.statut.value,
            "session_id": str(session.id) if session else None,
            "sessions_liees": len(sessions),
            "projet_id": str(projet.id) if projet else None,
            "etapes": etapes,
            "progression": {"faites": faites, "total": len(etapes)},
            "prochaine_action": prochaine,
        }

    # ── étapes M2 / M3 / préparation ────────────────────────────

    @staticmethod
    def _tdr(tdrs: list) -> dict:
        if not tdrs:
            return _etape("tdr", "TDR", "pending", "Aucun TDR généré pour cette opportunité.")
        valides = [t for t in tdrs if t.statut_validation == StatutValidation.VALIDE]
        if valides:
            return _etape("tdr", "TDR", "done", "TDR validé par un responsable.")
        return _etape("tdr", "TDR", "pending", "TDR généré, en attente de validation humaine.")

    @staticmethod
    def _offre(offres: list, champ: str, cle: str, titre: str) -> dict:
        avec = [o for o in offres if getattr(o, champ)]
        if avec:
            return _etape(cle, titre, "done", f"{len(avec)} version(s) enregistrée(s).")
        return _etape(cle, titre, "pending", f"Aucune {titre.lower()} enregistrée.")

    def _preparation(self, projet, _a_des_offres: bool) -> dict:
        if projet is None:
            return _etape("preparation", "Préparation · budget et planning", "pending",
                          "Aucun projet de préparation lié à cette opportunité.")
        budget = self.db.query(BudgetFormation).filter(BudgetFormation.projet_id == projet.id).first()
        nb_edt = self.db.query(func.count(EdtSession.id)).filter(EdtSession.projet_id == projet.id).scalar() or 0
        if budget and budget.valide and nb_edt > 0:
            return _etape("preparation", "Préparation · budget et planning", "done",
                          f"Budget validé · {nb_edt} séance(s) planifiée(s).")
        return _etape("preparation", "Préparation · budget et planning", "pending",
                      "Budget à valider ou planning à compléter.")

    # ── étapes M4 / M5 / M6 / M7 (dépendent de la session) ──────

    def _session_etapes(self, session) -> list[dict]:
        if session is None:
            attente = "Disponible après création de la session."
            return [
                _etape("formateur", "Formateur", "future", attente),
                _etape("session", "Session", "pending", "Aucune session créée pour cette opportunité."),
                _etape("participants", "Participants inscrits", "future", attente),
                _etape("supports", "Supports pédagogiques · RAG", "future", attente),
                _etape("seances", "Séances et présences", "future", attente),
                _etape("attestations", "Attestations", "future", attente),
                _etape("facturation", "Facturation", "future", attente),
            ]

        db = self.db
        nb_participants = db.query(func.count(Inscription.id)).filter(Inscription.session_id == session.id).scalar() or 0
        nb_seances = db.query(func.count(Seance.id)).filter(Seance.session_id == session.id).scalar() or 0
        attestations = db.query(func.count(Document.id)).filter(
            Document.session_id == session.id, Document.type == TypeDocument.ATTESTATION,
            Document.statut_validation == StatutValidation.VALIDE,
        ).scalar() or 0
        supports = [e for e in registre.entrees_pour_session(str(session.id)) if e.collection == "support"]
        indexes = sum(1 for e in supports if e.statut == "indexe")
        factures = db.query(Facture).filter(Facture.session_id == session.id).all()

        if supports and indexes == len(supports):
            etat_supports, detail_supports = "done", f"{indexes}/{len(supports)} support(s) indexé(s)."
        else:
            etat_supports = "pending"
            detail_supports = (f"{indexes}/{len(supports)} support(s) indexé(s)." if supports
                               else "Aucun support rattaché à la session.")

        return [
            _etape("formateur", "Formateur", "done" if session.formateur_id else "pending",
                   "Formateur affecté." if session.formateur_id else "Aucun formateur affecté."),
            _etape("session", "Session", "done",
                   f"{session.titre} · {session.date_debut:%d/%m/%Y} → {session.date_fin:%d/%m/%Y}"),
            _etape("participants", "Participants inscrits", "done" if nb_participants else "pending",
                   f"{nb_participants} participant(s) inscrit(s)." if nb_participants else "Aucun participant inscrit."),
            _etape("supports", "Supports pédagogiques · RAG", etat_supports, detail_supports),
            _etape("seances", "Séances et présences", "done" if nb_seances else "pending",
                   f"{nb_seances} séance(s) planifiée(s)." if nb_seances else "Aucune séance planifiée."),
            _etape("attestations", "Attestations", "done" if attestations else "pending",
                   f"{attestations} attestation(s) validée(s)." if attestations else "Aucune attestation validée."),
            self._facturation(factures),
        ]

    def _facturation(self, factures: list) -> dict:
        if not factures:
            return _etape("facturation", "Facturation", "pending", "Aucune facture liée à la session.")
        total = sum(f.montant_ttc for f in factures)
        ids = [f.id for f in factures]
        paye = self.db.query(func.coalesce(func.sum(Paiement.montant), 0.0)).filter(Paiement.facture_id.in_(ids)).scalar() or 0.0
        soldee = paye >= total - 0.01
        detail = f"{len(factures)} facture(s) · {total:,.0f} Ar TTC · encaissé {paye:,.0f} Ar".replace(",", " ")
        return _etape("facturation", "Facturation", "done" if soldee else "pending", detail)
