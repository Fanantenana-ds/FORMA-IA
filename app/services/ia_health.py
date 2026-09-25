# app/services/ia_health.py
# ============================================================
# ÉTAT DE SANTÉ GLOBAL DES MODULES IA (M3, Préparation, M5, M7, C3)
# ============================================================
# Chaque package (formations, offres, preparation, facturation, rag) charge
# ses agents avec try/except ImportError : un paquet manquant (ex. pandas)
# désactive un agent SANS erreur, seulement un avertissement noyé dans les
# logs. Les routes /ia/*/health répondaient alors "success: true" avec
# 4/7 agents.
#
# Ce module agrège l'état de tous les packages et distingue :
#   healthy  → tous les agents requis sont chargés
#   degraded → au moins un agent requis est indisponible (lister lesquels)
#
# 2026-09-25 (Étape H de la mission C3) : le module RAG est déclaré ici
# sous sa PROPRE clé "C3" (get_package_status() de app.services.rag),
# entièrement implémenté (7/7). ATTENTION, PIÈGE RÉEL TROUVÉ EN ÉCRIVANT
# CETTE ENTRÉE : app/services/formations/__init__.py (M5) contient DÉJÀ
# une entrée SANS RAPPORT nommée "Agent 7 — KnowledgeBase (RAG V2)"
# (app/services/formations/knowledge_base_service.py, un ancien projet V2
# jamais implémenté) — c'est CE "Agent 7"-là que OPTIONNELS protège
# depuis le début, pas le module C3. Retirer "Agent 7" d'OPTIONNELS
# casserait M5 (stabilisé, §27 de CLAUDE.md — ne pas toucher) en le
# faisant passer "degraded" à tort. OPTIONNELS reste donc INCHANGÉ ; le
# module C3 n'en a de toute façon pas besoin, ses 7 services étant déjà
# tous implémentés (voir get_package_status() de app/services/rag/__init__.py).
# ============================================================

import logging
from typing import Any, Dict, List

logger = logging.getLogger(__name__)

# Entrées volontairement non implémentées (ne comptent pas comme manquantes)
OPTIONNELS = ("Agent 7",)


def _est_optionnel(nom: str) -> bool:
    return any(nom.startswith(prefixe) for prefixe in OPTIONNELS)


def _packages() -> Dict[str, Any]:
    from app.services import facturation, formations, offres, preparation, rag

    return {
        "M5": formations,
        "M3": offres,
        "PREPARATION": preparation,
        "M7": facturation,
        "C3": rag,
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
