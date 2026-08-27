from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.core.dependencies import get_current_user
from app.models.opportunite import Opportunite
from app.models.user import User
from app.schemas.analyse import AnalyseResult
from app.services.analyse_service import AnalyseService

router = APIRouter(
    prefix="/opportunites",
    tags=["Analyse"]
)

@router.post("/{opportunite_id}/analyse", response_model=AnalyseResult)
def analyser_opportunite(opportunite_id: UUID, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    opportunite = (
        db.query(Opportunite)
        .filter(Opportunite.id == opportunite_id)
        .first()
    )

    if not opportunite:
        raise HTTPException(
            status_code=404,
            detail="Opportunite introuvable"
        )

    # Resultat temporaire
    resultat_ia = {
        "objet": opportunite.objet or "Analyse temporaire",
        "budget": opportunite.budget,
        "echeance": opportunite.echeance,
        "domaine": opportunite.domaine,
        "score_pertinente": 0.0
    }

    service = AnalyseService(db)

    opportunite = service.analyser(
        opportunite,
        resultat_ia,
        user_id=current_user.id
    )

    return AnalyseResult(
        objet=opportunite.objet,
        budget=opportunite.budget,
        echeance=opportunite.echeance,
        domaine=opportunite.domaine,
        score_pertinente=opportunite.score_pertinente
    )