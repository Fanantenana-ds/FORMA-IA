# app/services/backend_sync/base_sync.py
# ============================================================
# SOCLE COMMUN — Synchronisation IA → Backend
# ============================================================
# Ce module centralise tout ce qui est commun aux services de
# synchronisation (M1, M2, M3, Préparation, M5, M7) :
#
#   - lecture de la configuration (.env)
#   - authentification : token fixe OU login automatique
#   - re-login automatique + 1 nouvelle tentative sur HTTP 401
#   - skip gracieux si l'endpoint Backend est absent (404 / 405)
#   - vérification par GET après un POST (couche 2)
#
# Variables .env utilisées :
#   BACKEND_SYNC_ENABLED      true|false (défaut : false)
#   BACKEND_API_URL           (défaut : http://localhost:8000/api/v1)
#   BACKEND_SYNC_TOKEN        token JWT fixe (optionnel)
#   BACKEND_SERVICE_EMAIL     compte de service (login automatique)
#   BACKEND_SERVICE_PASSWORD
#   BACKEND_SYNC_TIMEOUT      en secondes (défaut : 30)
#
# ⚠️ Le compte de service doit avoir le rôle DIRECTION : les
#    routes Backend visées (sessions, documents, factures,
#    opportunités) sont réservées à DIRECTION / FORMATEUR /
#    ASSISTANT / COMPTABLE selon la route.
# ⚠️ Les IDs Backend sont des UUID (str), jamais des int.
# ⚠️ Ne jamais journaliser le token, le mot de passe ni les
#    payloads (données personnelles).
# ============================================================

import logging
import os
import uuid
from typing import Any, Dict, Optional

import httpx

logger = logging.getLogger(__name__)

_LOGIN_TIMEOUT = 10.0

# Token JWT obtenu par login automatique (mémoire du processus uniquement)
_token_cache: Optional[str] = None


# ============================================================
# CONFIGURATION (lue à chaque appel : robuste à l'ordre de
# chargement du .env)
# ============================================================

def _cfg() -> Dict[str, Any]:
    return {
        "enabled": os.getenv("BACKEND_SYNC_ENABLED", "false").lower() == "true",
        "api_url": os.getenv(
            "BACKEND_API_URL", "http://localhost:8000/api/v1"
        ).rstrip("/"),
        "token": os.getenv("BACKEND_SYNC_TOKEN", ""),
        "email": os.getenv("BACKEND_SERVICE_EMAIL", ""),
        "password": os.getenv("BACKEND_SERVICE_PASSWORD", ""),
        "timeout": float(os.getenv("BACKEND_SYNC_TIMEOUT", "30")),
    }


def is_sync_enabled() -> bool:
    """True si BACKEND_SYNC_ENABLED=true dans le .env."""
    return _cfg()["enabled"]


def reset_token_cache() -> None:
    """Vide le token en mémoire (utile pour les tests)."""
    global _token_cache
    _token_cache = None


# ============================================================
# AUTHENTIFICATION
# ============================================================

async def _login(
    cfg: Dict[str, Any],
    transport: Optional[httpx.AsyncBaseTransport] = None,
) -> Optional[str]:
    """Login automatique avec le compte de service (POST /auth/login)."""
    if not cfg["email"] or not cfg["password"]:
        logger.warning(
            "⚠️ Sync Backend : ni token valide ni identifiants de service "
            "— authentification impossible"
        )
        return None

    try:
        async with httpx.AsyncClient(
            timeout=_LOGIN_TIMEOUT, transport=transport
        ) as client:
            response = await client.post(
                f"{cfg['api_url']}/auth/login",
                json={"email": cfg["email"], "password": cfg["password"]},
            )
    except httpx.HTTPError as exc:
        logger.error("❌ Login Backend impossible : %s", type(exc).__name__)
        return None

    if response.status_code != 200:
        logger.error("❌ Login Backend refusé : HTTP %d", response.status_code)
        return None

    try:
        token = response.json().get("access_token")
    except ValueError:
        token = None

    if token:
        logger.info("✅ Token Backend obtenu via login automatique")
    return token


async def get_token(
    force_refresh: bool = False,
    transport: Optional[httpx.AsyncBaseTransport] = None,
) -> Optional[str]:
    """
    Retourne un JWT pour appeler le Backend.

    Ordre : token en cache → BACKEND_SYNC_TOKEN → login automatique.
    Avec force_refresh=True (après un 401) : login automatique uniquement.
    """
    global _token_cache
    cfg = _cfg()

    if force_refresh:
        _token_cache = None
    else:
        if _token_cache:
            return _token_cache
        if cfg["token"]:
            return cfg["token"]

    _token_cache = await _login(cfg, transport)
    return _token_cache


# ============================================================
# REQUÊTE HTTP
# ============================================================

async def backend_request(
    method: str,
    path: str,
    *,
    json: Any = None,
    params: Optional[Dict[str, Any]] = None,
    timeout: Optional[float] = None,
    transport: Optional[httpx.AsyncBaseTransport] = None,
) -> Dict[str, Any]:
    """
    Appelle le Backend avec authentification et re-login sur 401.

    Retourne toujours un dict (ne lève jamais d'exception réseau) :
      {
        "ok": bool,              # HTTP 2xx
        "status_code": int|None,
        "data": Any,             # JSON de la réponse (ou None)
        "error": str|None,
        "absent": bool,          # HTTP 404 / 405 (endpoint ou ressource absent)
      }
    """
    cfg = _cfg()
    result: Dict[str, Any] = {
        "ok": False,
        "status_code": None,
        "data": None,
        "error": None,
        "absent": False,
    }
    url = f"{cfg['api_url']}/{path.lstrip('/')}"
    token = await get_token(transport=transport)

    response: Optional[httpx.Response] = None
    for attempt in (1, 2):
        headers = {"Content-Type": "application/json"}
        if token:
            headers["Authorization"] = f"Bearer {token}"

        try:
            async with httpx.AsyncClient(
                timeout=timeout or cfg["timeout"], transport=transport
            ) as client:
                response = await client.request(
                    method, url, json=json, params=params, headers=headers
                )
        except httpx.TimeoutException:
            result["error"] = "Timeout Backend"
            return result
        except httpx.HTTPError as exc:
            result["error"] = f"Erreur réseau : {type(exc).__name__}"
            return result

        # Token expiré → un seul re-login puis nouvelle tentative
        if response.status_code == 401 and attempt == 1:
            logger.info("ℹ️ Token refusé (401) → nouveau login")
            token = await get_token(force_refresh=True, transport=transport)
            if token:
                continue
        break

    result["status_code"] = response.status_code

    if 200 <= response.status_code < 300:
        result["ok"] = True
        try:
            result["data"] = response.json() if response.content else None
        except ValueError:
            result["data"] = None
        return result

    result["absent"] = response.status_code in (404, 405)
    result["error"] = f"HTTP {response.status_code} : {response.text[:200]}"
    return result


# ============================================================
# RÉSULTAT STANDARD + POST AVEC VÉRIFICATION
# ============================================================

def new_result(**extra: Any) -> Dict[str, Any]:
    """Résultat de sync standard (même forme pour tous les services)."""
    result: Dict[str, Any] = {
        "enabled": is_sync_enabled(),
        "sent": False,        # créé côté Backend (HTTP 2xx)
        "skipped": False,     # endpoint absent (404/405) ou sync désactivée
        "verified": False,    # GET de contrôle réussi après le POST
        "resource_id": None,  # UUID (str) de la ressource créée
        "status_code": None,
        "data": None,
        "error": None,
    }
    result.update(extra)
    return result


async def post_and_verify(
    path: str,
    payload: Dict[str, Any],
    *,
    verify: bool = True,
    verify_path: Optional[str] = None,
    label: str = "ressource",
    transport: Optional[httpx.AsyncBaseTransport] = None,
) -> Dict[str, Any]:
    """
    POST vers le Backend, puis GET de contrôle (couche 2).

    Args:
        path: route de création (ex: "/sessions").
        payload: corps JSON.
        verify: False pour désactiver le GET de contrôle
            (quand le Backend n'expose pas de GET pour cette ressource).
        verify_path: route du GET, avec {id} (défaut : "<path>/{id}").
        label: nom lisible pour les logs (sans donnée personnelle).

    Comportement :
        - sync désactivée  → rien n'est envoyé (enabled=False)
        - HTTP 404 / 405   → skip gracieux (skipped=True)
        - autre erreur     → error renseigné, sans exception
    """
    result = new_result()
    if not result["enabled"]:
        logger.info(
            "ℹ️ Backend sync DÉSACTIVÉ (BACKEND_SYNC_ENABLED=false) — "
            "%s non envoyé", label
        )
        return result

    response = await backend_request(
        "POST", path, json=payload, transport=transport
    )
    result["status_code"] = response["status_code"]

    if response["absent"]:
        result["skipped"] = True
        result["error"] = f"Endpoint Backend absent ({response['error']})"
        logger.warning("⚠️ Sync %s ignorée : %s", label, result["error"])
        return result

    if not response["ok"]:
        result["error"] = response["error"]
        logger.warning("❌ Sync %s échouée : %s", label, result["error"])
        return result

    data = response["data"]
    result["sent"] = True
    result["data"] = data
    if isinstance(data, dict) and data.get("id") is not None:
        result["resource_id"] = str(data["id"])

    if verify and result["resource_id"]:
        check_path = (verify_path or f"{path.rstrip('/')}/{{id}}").format(
            id=result["resource_id"]
        )
        check = await backend_request("GET", check_path, transport=transport)
        result["verified"] = check["ok"]
        if not check["ok"]:
            logger.warning(
                "⚠️ Sync %s : créé mais GET de contrôle en échec (%s)",
                label, check["error"]
            )

    logger.info(
        "✅ Sync %s : id=%s vérifié=%s",
        label, result["resource_id"], result["verified"]
    )
    return result


# ============================================================
# UTILITAIRES
# ============================================================

def is_valid_uuid(value: Any) -> bool:
    """True si value est un UUID valide (str ou UUID)."""
    try:
        uuid.UUID(str(value))
        return True
    except (ValueError, AttributeError, TypeError):
        return False


def truncate(value: Any, max_len: int) -> str:
    """Tronque à max_len (colonnes VARCHAR limitées côté Backend)."""
    return str(value or "").strip()[:max_len]
