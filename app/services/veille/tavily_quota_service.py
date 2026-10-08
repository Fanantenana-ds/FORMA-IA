# app/services/veille/tavily_quota_service.py
# ============================================================
# QUOTA TAVILY — compteur persistant d'appels HTTP RÉELS (M1, Étape B)
# ============================================================
# Compte les APPELS HTTP réels vers Tavily (TavilyService._do_request),
# pas les "requêtes" utilisateur : une seule recherche peut déclencher
# jusqu'à 2 appels HTTP (principal + repli), chacun rejouable jusqu'à
# RETRY_MAX_ATTEMPTS fois par app.utils.retry.retry_with_backoff. Un
# cache hit (TavilyService._get_from_cache) ne déclenche AUCUN appel
# HTTP et n'est donc jamais compté ici.
#
# Persistance : data/tavily_quota.json (écriture atomique, même motif
# que hitl_helper.py / review_sync.py / registry_service.py).
#
# Variables d'environnement (valeurs par défaut si absentes) :
#   TAVILY_QUOTA_MENSUEL         1000   quota mensuel "souple" (référence %)
#   TAVILY_BUDGET_AUTO           600    budget mensuel dédié au mode auto
#   TAVILY_QUOTA_PLAFOND_DUR     980    plafond dur, tous modes confondus
#   VEILLE_AUTO_MAX_RUNS_PER_DAY 2      passages auto max par jour calendaire
#   TAVILY_QUOTA_RESET_DAY       1      jour du mois qui démarre la période
#
# Catégories : "auto" (détection planifiée/déclenchée), "manuel"
# (POST /ia/veille/rechercher), "collecte" (scripts de collecte corpus,
# Étape E — pas encore appelée avec cette catégorie à ce jour).
# ============================================================

import json
import logging
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parents[3]
QUOTA_PATH = BASE_DIR / "data" / "tavily_quota.json"

CATEGORIES = ("auto", "manuel", "collecte")
RETENTION_JOURS_RUNS = 30


class QuotaTavilyDepasseError(Exception):
    """Plafond dur Tavily atteint pour un appel manuel/collecte — la route
    appelante convertit ceci en HTTP 429 avec un message clair."""


# ============================================================
# CONFIGURATION (lue à chaque appel, comme auto_detection_service)
# ============================================================

def _env_int(nom: str, defaut: int) -> int:
    try:
        return int(os.getenv(nom, str(defaut)))
    except ValueError:
        return defaut


def config() -> Dict[str, int]:
    return {
        "quota_mensuel": _env_int("TAVILY_QUOTA_MENSUEL", 1000),
        "budget_auto": _env_int("TAVILY_BUDGET_AUTO", 600),
        "plafond_dur": _env_int("TAVILY_QUOTA_PLAFOND_DUR", 980),
        "max_runs_par_jour": _env_int("VEILLE_AUTO_MAX_RUNS_PER_DAY", 2),
        "jour_reset": max(1, min(28, _env_int("TAVILY_QUOTA_RESET_DAY", 1))),
    }


# ============================================================
# PÉRIODE (mois calendaire, décalé par TAVILY_QUOTA_RESET_DAY)
# ============================================================

def _periode(maintenant: datetime, jour_reset: int) -> str:
    annee, mois = maintenant.year, maintenant.month
    if maintenant.day < jour_reset:
        mois -= 1
        if mois == 0:
            mois, annee = 12, annee - 1
    return f"{annee:04d}-{mois:02d}"


# ============================================================
# PERSISTANCE (écriture atomique)
# ============================================================

def _charger() -> Dict[str, Any]:
    if not QUOTA_PATH.exists():
        return {}
    try:
        with open(QUOTA_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError):
        logger.error("❌ data/tavily_quota.json illisible — réinitialisation.")
        return {}


def _sauvegarder(data: Dict[str, Any]) -> None:
    QUOTA_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = QUOTA_PATH.with_suffix(".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, QUOTA_PATH)


def _nettoyer_runs_par_jour(runs_par_jour: Dict[str, int], maintenant: datetime) -> Dict[str, int]:
    """Retire les entrées de plus de 30 jours (point 3 de la mission)."""
    limite = maintenant - timedelta(days=RETENTION_JOURS_RUNS)
    propre = {}
    for cle, valeur in runs_par_jour.items():
        try:
            date_cle = datetime.strptime(cle, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        except ValueError:
            continue  # clé corrompue : abandonnée
        if date_cle >= limite:
            propre[cle] = valeur
    return propre


def _etat(maintenant: Optional[datetime] = None) -> Dict[str, Any]:
    """Charge l'état ; réinitialise les compteurs d'APPELS si la période a
    changé (les runs/jour sont indépendants — nettoyés par ancienneté,
    pas par bascule de mois)."""
    maintenant = maintenant or datetime.now(timezone.utc)
    cfg = config()
    periode_actuelle = _periode(maintenant, cfg["jour_reset"])

    data = _charger()
    runs_par_jour = _nettoyer_runs_par_jour(data.get("runs_par_jour", {}), maintenant)

    if data.get("periode") != periode_actuelle:
        data = {"periode": periode_actuelle, "appels": {c: 0 for c in CATEGORIES}}

    data.setdefault("appels", {})
    for c in CATEGORIES:
        data["appels"].setdefault(c, 0)
    data["runs_par_jour"] = runs_par_jour
    return data


# ============================================================
# ENREGISTREMENT (appelé depuis TavilyService._do_request)
# ============================================================

def enregistrer_appel(categorie: str, maintenant: Optional[datetime] = None) -> None:
    """Incrémente le compteur d'UN appel HTTP réel (échec/retry compris).
    Ne jamais appeler depuis un cache hit."""
    if categorie not in CATEGORIES:
        categorie = "manuel"
    maintenant = maintenant or datetime.now(timezone.utc)
    cfg = config()

    data = _etat(maintenant)
    data["appels"][categorie] += 1
    _sauvegarder(data)

    total = sum(data["appels"].values())
    pourcentage = (total / cfg["quota_mensuel"] * 100) if cfg["quota_mensuel"] else 0.0
    if pourcentage >= 95:
        logger.error(
            "❌ Quota Tavily critique : %d/%d appels ce mois (%.0f%%, catégorie=%s)",
            total, cfg["quota_mensuel"], pourcentage, categorie,
        )
    elif pourcentage >= 80:
        logger.warning(
            "⚠️ Quota Tavily élevé : %d/%d appels ce mois (%.0f%%, catégorie=%s)",
            total, cfg["quota_mensuel"], pourcentage, categorie,
        )


def enregistrer_run_auto(maintenant: Optional[datetime] = None) -> None:
    """Incrémente le compteur de passages auto RÉELLEMENT lancés (pas les
    tentatives bloquées par le quota ou le verrou)."""
    maintenant = maintenant or datetime.now(timezone.utc)
    data = _etat(maintenant)
    cle = maintenant.strftime("%Y-%m-%d")
    data["runs_par_jour"][cle] = data["runs_par_jour"].get(cle, 0) + 1
    _sauvegarder(data)


# ============================================================
# LECTURE
# ============================================================

def consommation(categorie: Optional[str] = None, maintenant: Optional[datetime] = None) -> int:
    data = _etat(maintenant)
    if categorie:
        return data["appels"].get(categorie, 0)
    return sum(data["appels"].values())


def runs_aujourd_hui(maintenant: Optional[datetime] = None) -> int:
    maintenant = maintenant or datetime.now(timezone.utc)
    data = _etat(maintenant)
    return data["runs_par_jour"].get(maintenant.strftime("%Y-%m-%d"), 0)


def plafond_dur_atteint(maintenant: Optional[datetime] = None) -> bool:
    cfg = config()
    return consommation(None, maintenant) >= cfg["plafond_dur"]


# ============================================================
# VÉRIFICATIONS PRÉALABLES
# ============================================================

def verifier_quota_auto(maintenant: Optional[datetime] = None) -> Tuple[bool, Optional[str]]:
    """Vérification UNIQUE avant de lancer un passage auto (pas par appel
    HTTP individuel) — appelée depuis executer_detection, après le verrou
    anti-chevauchement. Retourne (autorise, raison_si_refuse)."""
    maintenant = maintenant or datetime.now(timezone.utc)
    cfg = config()

    runs = runs_aujourd_hui(maintenant)
    if runs >= cfg["max_runs_par_jour"]:
        return False, (
            f"Limite de {cfg['max_runs_par_jour']} passage(s) automatique(s) par jour "
            f"atteinte ({runs} déjà exécuté(s) aujourd'hui)."
        )

    conso_auto = consommation("auto", maintenant)
    if conso_auto >= cfg["budget_auto"]:
        return False, (
            f"Budget Tavily du mode auto épuisé : {conso_auto}/{cfg['budget_auto']} "
            f"appels ce mois."
        )

    total = consommation(None, maintenant)
    if total >= cfg["plafond_dur"]:
        return False, (
            f"Plafond dur Tavily atteint : {total}/{cfg['plafond_dur']} appels ce mois "
            f"(tous modes confondus)."
        )

    return True, None


# ============================================================
# ROUTE — GET /ia/veille/quota
# ============================================================

def etat_pour_route(maintenant: Optional[datetime] = None) -> Dict[str, Any]:
    maintenant = maintenant or datetime.now(timezone.utc)
    cfg = config()
    data = _etat(maintenant)
    total = sum(data["appels"].values())
    pourcentage = round((total / cfg["quota_mensuel"] * 100), 1) if cfg["quota_mensuel"] else 0.0

    avertissement = None
    if pourcentage >= 95:
        avertissement = "critique"
    elif pourcentage >= 80:
        avertissement = "eleve"

    return {
        "periode": data["periode"],
        "appels_par_categorie": dict(data["appels"]),
        "total_appels": total,
        "restant": max(0, cfg["quota_mensuel"] - total),
        "pourcentage_utilise": pourcentage,
        "runs_auto_aujourd_hui": runs_aujourd_hui(maintenant),
        "configuration": cfg,
        "avertissement": avertissement,
    }
