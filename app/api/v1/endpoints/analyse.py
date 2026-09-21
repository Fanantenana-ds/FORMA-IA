from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.core.dependencies import get_current_user
from app.models.opportunite import Opportunite
from app.models.user import User
from app.schemas.analyse import AnalyseResult
from app.services.analyse_service import AnalyseService
from app.services.veille.opportunity_analysis_service import OpportuniteAnalyseIAService

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

    # Analyse IA (M1) : extraction + classification + scoring (0.0 a 1.0)
    resultat_ia = OpportuniteAnalyseIAService().analyser(
        contenu=opportunite.contenu,
        objet=opportunite.objet,
        budget=opportunite.budget,
        echeance=opportunite.echeance,
        domaine=opportunite.domaine,
        source=opportunite.source.value,
    )

    # La colonne opportunites.score_pertinence n'etait jamais alimentee :
    # AnalyseService ne renseigne que l'historique et le statut.
    opportunite.score_pertinence = resultat_ia["score_pertinence"]

    service = AnalyseService(db)

    service.analyser(
        opportunite,
        resultat_ia,
        user_id=current_user.id
    )

    return AnalyseResult(
        objet=resultat_ia["objet"],
        budget=resultat_ia["budget"],
        echeance=resultat_ia["echeance"],
        domaine=resultat_ia["domaine"],
        score_pertinence=resultat_ia["score_pertinence"]
    )
