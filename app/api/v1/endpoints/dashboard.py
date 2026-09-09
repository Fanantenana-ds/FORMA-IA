from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.core.dependencies import require_role
from app.models.user import User
from app.schemas.dashboard import StatistiquesResponse
from app.services.dashboard_service import DashboardService

router = APIRouter(prefix="/dasboard", tags=["Dashboard"])


def get_dashboard_service(db: Session = Depends(get_db)) -> DashboardService:
    return DashboardService(db)


@router.get("/Statistiques", response_model=StatistiquesResponse)
def get_statisiques(
    service: DashboardService = Depends(get_dashboard_service),
    current_user: User = Depends(require_role("DIRECTION"))
):
    return service.obtenir_statistiques()