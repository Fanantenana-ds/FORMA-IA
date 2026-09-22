# app/services/ia_health.py
# ============================================================
# ÉTAT DE SANTÉ GLOBAL DES MODULES IA (M3, Préparation, M5)
# ============================================================
# Chaque package (formations, offres, preparation) charge ses agents avec
# try/except ImportError : un paquet manquant (ex. pandas) désactive un agent
# SANS erreur, seulement un avertissement noyé dans les logs. Les routes
# /ia/*/health répondaient alors "success: true" avec 4/7 agents.
#
# Ce module agrège l'état des trois packages et distingue :
#   healthy  → tous les agents requis sont chargés
#   degraded → au moins un agent requis est indisponible (lister lesquels)
#
# Les agents « à venir » (Agent 7 — RAG V2) sont optionnels : leur absence
# n'est pas une dégradation.
# ============================================================

import logging
from typing import Any, Dict, List

logger = logging.getLogger(__name__)

# Entrées volontairement non implémentées (ne comptent pas comme manquantes)
OPTIONNELS = ("Agent 7",)


def _est_optionnel(nom: str) -> bool:
    return any(nom.startswith(prefixe) for prefixe in OPTIONNELS)


def _packages() -> Dict[str, Any]:
    from app.services import facturation, formations, offres, preparation

    return {
        "M5": formations,
        "M3": offres,
        "PREPARATION": preparation,
        "M7": facturation,
    }


def collecter() -> Dict[str, Any]:
    """État de chaque module + statut global."""
    modules: Dict[str, Any] = {}
    manquants_global: List[str] = []

    for code, package in _packages().items():
        etat = package.get_package_status()
        elements: Dict[str, bool] = etat.get("agents") or etat.get("services") or {}

        manquants = [
            nom for nom, charge in elements.items()
            if not charge and not _est_optionnel(nom)
        ]
        modules[code] = {
            "version": etat.get("version"),
            "charges": sum(1 for charge in elements.values() if charge),
            "total": len(elements),
            "manquants": manquants,
        }
        manquants_global.extend(f"{code} — {nom}" for nom in manquants)

    return {
        "status": "degraded" if manquants_global else "healthy",
        "manquants": manquants_global,
        "modules": modules,
    }


def journaliser_au_demarrage() -> Dict[str, Any]:
    """Alerte visible (ERROR) si un agent requis est indisponible."""
    etat = collecter()
    if etat["status"] == "degraded":
        logger.error(
            "❌ Modules IA DÉGRADÉS — agents indisponibles : %s "
            "(cause probable : dépendance manquante, voir les avertissements "
            "d'import au démarrage)",
            ", ".join(etat["manquants"]),
        )
    else:
        logger.info("✅ Modules IA : tous les agents requis sont chargés")
    return etat
