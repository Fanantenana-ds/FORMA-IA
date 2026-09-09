from datetime import datetime, timezone
from uuid import UUID
from fastapi import HTTPException
from sqlalchemy.orm import Session
from typing import List

from app.models.document import Document, TDR, Attestation, StatutValidation, FormatExport, Offre
from app.models.formation import Session as FormationSession, Seance, Presence, Participant, StatutPresence
from app.models.opportunite import Opportunite
from app.schemas.document import TDRRequest, OffreRequest




class DocumentService:
    def __init__(self, db: Session):
        self.db = db

    def generer_tdr(self, brief: TDRRequest) -> TDR:
        contenu = (
            f"TDR - Client: {brief.client}\n"
            f"Objectifs: {brief.objectifs}\n"
            f"Budget: {brief.budget}\n"
            f"Échéance: {brief.echeance}"
        )

        tdr = TDR(
            client=brief.client,
            objectifs=brief.objectifs,
            contenu=contenu,
            opportunite_id=brief.opportunite_id,
            statut_validation=StatutValidation.EN_ATTENTE
        )
        self.db.add(tdr)
        self.db.commit()
        self.db.refresh(tdr)
        return tdr

    def valider(self, document_id: UUID, user_id: UUID, approuve: bool) -> Document:
        document = self.db.query(Document).filter(Document.id == document_id).first()

        if not document:
            raise HTTPException(status_code=404, detail="Document introuvable")

        document.statut_validation = StatutValidation.VALIDE if approuve else StatutValidation.REJETE
        document.valide_par = user_id
        document.date_validation = datetime.now(timezone.utc)
        self.db.commit()
        self.db.refresh(document)
        return document

    def generer_attestations(self, session_id: UUID) -> List[Attestation]:
        session = self.db.query(FormationSession).filter(FormationSession.id == session_id).first()
        if not session:
            raise HTTPException(status_code=404, detail= "Session introuvable")

        # Participant ayant été PRÉSENT au moin une fois à une séance de la session
        participants = (
            self.db.query(Participant)
            .join(Presence, Presence.participant_id == Participant.id)
            .join(Seance, Seance.id == Presence.seance_id)
            .filter(Seance.session_id == session_id, Presence.statut == StatutPresence.PRESENT)
            .distinct()
            .all()
        )

        existantes = self.db.query(Attestation).filter(Attestation.session_id == session_id).all()
        deja_generees = {a.participant_id for a in existantes}
        sequence = len(existantes) + 1

        for participant in participants:
            if participant.id in deja_generees:
                continue

            numero = f"ATT-{str(session_id)[:8].upper()}-{sequence:03d}"
            sequence += 1

            attestation = Attestation(
                session_id=session_id,
                participant_id=participant.id,
                numero_unique=numero,
                contenu=f"Attestation de participation - {participant.nom} - {session.titre}",
                format_export=FormatExport.PDF,
                statut_validation=StatutValidation.EN_ATTENTE
            )
            self.db.add(attestation)

        self.db.commit()

        return self.db.query(Attestation).filter(Attestation.session_id == session_id).all()

    def generer_offre(self, data: OffreRequest) -> Offre:
        opportunite = self.db.query(Opportunite).filter(Opportunite.id == data.opportunite_id).first()
        if not opportunite:
            raise HTTPException(status_code=404, detail="Opportunite introuvable")

        contenu = (
            f"Offre technique et financière\n"
            f"Objet: {opportunite.objet or '-'}\n"
            f"Domaine: {opportunite.domaine or '-'}\n"
            f"Montant proposé: {data.montant or opportunite.budget or '-'}"
        )

        offre = Offre(
            opportunite_id = opportunite.id,
            montant = data.montant,
            contenu = contenu,
            statut_validation = StatutValidation.EN_ATTENTE
        )
        self.db.add(offre)
        self.db.commit()
        self.db.refresh(offre)
        return offre