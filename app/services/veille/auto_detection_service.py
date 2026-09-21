# app/services/veille/auto_detection_service.py
# ============================================================
# M1 — DÉTECTION AUTOMATIQUE D'OPPORTUNITÉS (sans requête saisie)
# ============================================================
# Deux façons d'obtenir des opportunités en M1 :
#
#   MODE 1 — RECHERCHE       POST /ia/veille/rechercher
#            L'utilisateur saisit une requête (existant).
#
#   MODE 2 — DÉTECTION AUTO  POST /ia/veille/detecter
#            Aucune requête : le système lance lui-même les requêtes du
#            profil ALTIORA (ci-dessous), à la demande OU par
#            planification (désactivée par défaut).
#
# Ce module porte : le profil de requêtes, le verrou anti-chevauchement,
# l'état de la dernière exécution (data/veille_auto_state.json) et la
# planification. La logique de détection elle-même est dans
# VeilleOrchestrator.detecter_automatiquement.
#
# Chaque passage consomme du quota Tavily + Groq (1 recherche + 1 à 2 appels
# LLM par requête) : la planification est donc OFF tant qu'on ne l'active pas.
#
# Variables d'environnement :
#   VEILLE_AUTO_ENABLED         "false"  active la planification
#   VEILLE_AUTO_INTERVAL_HOURS  "24"     délai entre deux passages (min 1)
#   VEILLE_AUTO_QUERIES         ""       requêtes séparées par ";" (sinon défaut)
#   VEILLE_AUTO_MAX_QUERIES     "5"      nombre max de requêtes par passage
#   VEILLE_AUTO_MIN_SCORE       "40"     score minimal conservé (0-100)
#   VEILLE_AUTO_LIMIT           "20"     nombre max d'opportunités par passage
# ============================================================

import asyncio
import json
import logging
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parents[3]
STATE_PATH = BASE_DIR / "data" / "veille_auto_state.json"

DELAI_PREMIER_PASSAGE_S = 60.0     # après le démarrage, si jamais exécuté
ATTENTE_MAX_ENTRE_VERIFICATIONS_S = 3600.0

# Profil ALTIORA Prest : formation / conseil en IA, data, DevOps, développement.
# "Madagascar" est ajouté automatiquement par le pipeline M1.
REQUETES_PAR_DEFAUT: List[str] = [
    "appel d'offres formation intelligence artificielle IA",
    "appel d'offres formation data science analyse de données",
    "appel d'offres formation DevOps cloud",
    "appel d'offres formation développement web mobile",
    "recrutement formateur consultant IA data",
]


class DetectionAutoEnCours(Exception):
    """Une détection automatique est déjà en cours d'exécution."""


_en_cours = False
_tache: Optional["asyncio.Task"] = None
_demarre_a: Optional[datetime] = None


# ============================================================
# CONFIGURATION (lue à chaque appel : modifiable sans redémarrage des tests)
# ============================================================

def _env_int(nom: str, defaut: int, minimum: int = 0) -> int:
    try:
        return max(minimum, int(os.getenv(nom, str(defaut))))
    except ValueError:
        return defaut


def planification_activee() -> bool:
    return os.getenv("VEILLE_AUTO_ENABLED", "false").strip().lower() in {
        "1", "true", "yes", "oui",
    }


def intervalle_heures() -> int:
    return _env_int("VEILLE_AUTO_INTERVAL_HOURS", 24, minimum=1)


def score_minimum() -> int:
    return min(100, _env_int("VEILLE_AUTO_MIN_SCORE", 40))


def limite() -> int:
    return _env_int("VEILLE_AUTO_LIMIT", 20, minimum=1)


def get_queries() -> List[str]:
    """Requêtes du passage : VEILLE_AUTO_QUERIES ou profil par défaut, bornées."""
    brut = os.getenv("VEILLE_AUTO_QUERIES", "")
    requetes = [q.strip() for q in brut.split(";") if q.strip()] or list(
        REQUETES_PAR_DEFAUT
    )
    return requetes[: _env_int("VEILLE_AUTO_MAX_QUERIES", 5, minimum=1)]


def get_config() -> Dict[str, Any]:
    return {
        "planification_activee": planification_activee(),
        "intervalle_heures": intervalle_heures(),
        "requetes": get_queries(),
        "score_minimum": score_minimum(),
        "limite": limite(),
    }


# ============================================================
# ÉTAT DE LA DERNIÈRE EXÉCUTION
# ============================================================

def lire_etat() -> Dict[str, Any]:
    try:
        with open(STATE_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def _ecrire_etat(etat: Dict[str, Any]) -> None:
    try:
        STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
        tmp = STATE_PATH.with_suffix(".tmp")
        tmp.write_text(json.dumps(etat, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(STATE_PATH)
    except OSError as exc:
        logger.warning("⚠️ État de détection automatique non enregistré : %s", exc)


def est_en_cours() -> bool:
    return _en_cours


# ============================================================
# EXÉCUTION D'UN PASSAGE
# ============================================================

async def executer_detection(
    orchestrator,
    declenchement: str = "manuel",
    min_score: Optional[int] = None,
    limit: Optional[int] = None,
    sync_backend: bool = True,
) -> Dict[str, Any]:
    """
    Lance un passage de détection automatique.

    Lève DetectionAutoEnCours si un passage est déjà actif (deux passages
    en parallèle doubleraient la consommation de quota).
    L'état est enregistré même en cas d'échec, pour que la planification
    n'enchaîne pas de nouvelles tentatives à la suite.
    """
    global _en_cours
    if _en_cours:
        raise DetectionAutoEnCours()

    _en_cours = True
    debut = datetime.now(timezone.utc)
    etat: Dict[str, Any] = {
        "derniere_execution": debut.isoformat(),
        "declenchement": declenchement,
        "statut": "error",
        "erreur": None,
    }
    try:
        resultat = await orchestrator.detecter_automatiquement(
            queries=get_queries(),
            min_score=score_minimum() if min_score is None else min_score,
            limit=limite() if limit is None else limit,
            sync_backend=sync_backend,
        )
        sync = (resultat.get("statistics") or {}).get("backend_sync") or {}
        etat.update({
            "statut": resultat.get("status"),
            "requetes": len(resultat.get("queries") or []),
            "total": resultat.get("total", 0),
            "envoyees": sync.get("sent", 0),
            "deja_presentes": sync.get("already_present", 0),
            "echecs_envoi": sync.get("failed", 0),
        })
        return resultat
    except Exception as exc:
        etat["erreur"] = f"{type(exc).__name__}: {exc}"
        raise
    finally:
        _en_cours = False
        _ecrire_etat(etat)


# ============================================================
# PLANIFICATION (optionnelle)
# ============================================================

def secondes_avant_prochaine_execution(maintenant: Optional[datetime] = None) -> float:
    """0 = passage dû maintenant. Tient compte des passages manuels et des redémarrages."""
    maintenant = maintenant or datetime.now(timezone.utc)
    derniere = lire_etat().get("derniere_execution")

    if derniere:
        try:
            echeance = datetime.fromisoformat(derniere) + timedelta(hours=intervalle_heures())
            return max(0.0, (echeance - maintenant).total_seconds())
        except ValueError:
            pass  # état illisible : traité comme « jamais exécuté »

    debut = _demarre_a or maintenant
    return max(0.0, DELAI_PREMIER_PASSAGE_S - (maintenant - debut).total_seconds())


async def _boucle_planifiee(orchestrator) -> None:
    while True:
        attente = secondes_avant_prochaine_execution()
        if attente > 0:
            # Réévalue régulièrement : un passage manuel décale la prochaine échéance.
            await asyncio.sleep(min(attente, ATTENTE_MAX_ENTRE_VERIFICATIONS_S))
            continue
        try:
            logger.info("⏰ Détection automatique planifiée : démarrage")
            await executer_detection(orchestrator, declenchement="planifie")
        except DetectionAutoEnCours:
            logger.info("⏰ Détection automatique déjà en cours — passage ignoré")
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("❌ Détection automatique planifiée en échec")
        await asyncio.sleep(DELAI_PREMIER_PASSAGE_S)   # jamais de boucle serrée


def demarrer_planification(orchestrator) -> Optional["asyncio.Task"]:
    """Démarre la planification si VEILLE_AUTO_ENABLED=true (sinon ne fait rien)."""
    global _tache, _demarre_a
    if not planification_activee():
        logger.info("⏸️ Détection automatique planifiée : désactivée (VEILLE_AUTO_ENABLED)")
        return None
    if _tache is not None and not _tache.done():
        return _tache

    _demarre_a = datetime.now(timezone.utc)
    _tache = asyncio.get_running_loop().create_task(_boucle_planifiee(orchestrator))
    logger.info(
        "⏰ Détection automatique planifiée : toutes les %d h (%d requête(s))",
        intervalle_heures(), len(get_queries()),
    )
    return _tache


async def arreter_planification() -> None:
    global _tache
    if _tache is not None and not _tache.done():
        _tache.cancel()
        try:
            await _tache
        except asyncio.CancelledError:
            pass
    _tache = None
