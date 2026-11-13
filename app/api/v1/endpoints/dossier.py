# app/api/v1/endpoints/dossier.py
# GET /dossiers/{opportunite_id}/etat — état complet d'un dossier (étapes M1→M7) en une requête.

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.dependencies import require_role
from app.database import get_db
from app.models.user import User
from app.services.dossier_service import DossierService

router = APIRouter(prefix="/dossiers", tags=["Dossiers de formation"])


@router.get("/{opportunite_id}/etat", summary="État d'un dossier : étapes, progression, prochaine action")
def etat_dossier(
    opportunite_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("DIRECTION", "ASSISTANT")),
):
    etat = DossierService(db).obtenir_etat(opportunite_id)
    if etat is None:
        raise HTTPException(status_code=404, detail="Opportunité introuvable.")
    return etat
