# app/api/v1/endpoints/dashboard.py
# ============================================================
# ROUTES BACKEND — Dashboard / Statistiques (M8a)
# ============================================================
#
# GET /dashboard/statistiques
#   Retourne les indicateurs clés de la plateforme ALTIORA en une
#   seule requête, groupés en 4 sections :
#     • Formations   — sessions réalisées, participants, taux de présence
#     • Opportunités — total, répartition par domaine et par statut
#     • Documents    — TDR, offres, attestations générés
#     • Facturation  — CA facturé/encaissé, factures en retard,
#                      montant impayé, relances envoyées
#
# ⚙️  Rôles : DIRECTION uniquement
# ============================================================

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.dependencies import require_role
from app.database import get_db
from app.models.user import User
from app.schemas.dashboard import StatistiquesResponse
from app.services.dashboard_service import DashboardService

router = APIRouter(prefix="/dashboard", tags=["Dashboard M8a"])


def get_dashboard_service(db: Session = Depends(get_db)) -> DashboardService:
    return DashboardService(db)


@router.get(
    "/statistiques",
    response_model=StatistiquesResponse,
    summary="Tableau de bord — indicateurs clés de la plateforme",
    description=(
        "Retourne en une seule requête tous les indicateurs de la plateforme ALTIORA.\n\n"
        "**Section Formations :**\n"
        "- `session_realisees` : nombre total de sessions créées\n"
        "- `participant` : nombre de participants distincts ayant au moins une présence\n"
        "- `taux_presence` : pourcentage de présences effectives (PRESENT / total)\n\n"
        "**Section Opportunités :**\n"
        "- `opportunite_total` : nombre total d'opportunités enregistrées\n"
        "- `opportunite_par_domaine` : `{ \"IA\": 3, \"DEVOPS\": 2, ... }`\n"
        "- `opportunite_par_statut` : `{ \"EN_ATTENTE\": 5, \"ANALYSEE\": 3, \"ARCHIVEE\": 1 }`\n\n"
        "**Section Documents :**\n"
        "- `tdr_generes` : nombre de TDR générés\n"
        "- `offres_generees` : nombre d'offres générées\n"
        "- `attestations_generees` : nombre d'attestations émises\n\n"
        "**Section Facturation :**\n"
        "- `chiffre_affaires_facture` : somme des montants HT facturés (toutes factures)\n"
        "- `chiffre_affaires_encaisse` : somme des paiements reçus\n"
        "- `factures_en_retard` : nombre de factures au statut EN_RETARD\n"
        "- `montant_impaye` : montant TTC restant dû sur les factures non soldées\n"
        "- `relances_envoyees` : nombre de relances IA approuvées et persistées\n\n"
        "**Rôles autorisés :** DIRECTION."
    ),
)
def get_statistiques(
    service: DashboardService = Depends(get_dashboard_service),
    current_user=Depends(require_role("DIRECTION")),
):
    return service.obtenir_statistiques()
