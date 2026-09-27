"""
=============================================================================
PACKAGE : app.services.rh
=============================================================================
Module   : Assistance RH — M4 (bonus)
Rôle     : 5 agents RH — présélection CV, compte-rendu entretien,
           email RH, contrat formateur, évaluation formateur post-session.

Auteur  : Équipe IA — ALTIORA Prest
Version : 1.0.0
=============================================================================
"""

__version__ = "1.0.0"

__all__ = [
    "CvPreselecteurService",
    "EntretienService",
    "EmailRhService",
    "ContratFormateurService",
    "EvaluationFormateurService",
]

from .cv_preselecteur_service import CvPreselecteurService
from .entretien_service import EntretienService
from .email_rh_service import EmailRhService
from .contrat_formateur_service import ContratFormateurService
from .evaluation_formateur_service import EvaluationFormateurService
