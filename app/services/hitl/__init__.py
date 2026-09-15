"""
=============================================================================
PACKAGE : app.services.hitl
=============================================================================
Module   : Human-In-The-Loop (HITL) — Générique
Rôle     : Fournit une couche de validation humaine réutilisable par
           TOUS les modules du projet FORMA-IA.

Auteur  : Équipe IA — ALTIORA Prest
Version : 2.0.0
=============================================================================
"""

import logging

logger = logging.getLogger(__name__)


__version__ = "2.0.0"
__author__ = "Équipe IA — ALTIORA Prest"

__all__ = [
    "__version__",
    "create_review",
    "list_pending",
    "get_review",
    "approve_review",
    "reject_review",
    "get_stats",
    "AGENT_CRITICITY",
]


from .hitl_helper import (
    create_review,
    list_pending,
    get_review,
    approve_review,
    reject_review,
    get_stats,
    AGENT_CRITICITY,
)


logger.info(
    f"📦 Package 'hitl' (Human-In-The-Loop v{__version__}) chargé — "
    f"Fonctions : create_review, approve_review, reject_review, get_stats"
)