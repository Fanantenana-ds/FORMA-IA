from datetime import datetime, timezone
from uuid import UUID
from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.document import Document, TDR, StatutValidation
from app.schemas.document import TDRRequest


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