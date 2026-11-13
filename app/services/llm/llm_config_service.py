# app/services/llm/llm_config_service.py
# ============================================================
# SERVICE DE CONFIGURATION LLM — runtime sans redémarrage
# ============================================================
# Lit/écrit data/llm_config.json (priorité sur .env).
# Les clés API sont chiffrées avec Fernet (clé dérivée du JWT secret).
# Aucune clé n'est jamais retournée en clair dans les réponses API.
# ============================================================

import json
import logging
import os
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_CONFIG_FILE = Path("data") / "llm_config.json"

# ── Catalogue des modèles disponibles par provider ──────────────────────────
MODELES_DISPONIBLES: dict[str, list[dict[str, Any]]] = {
    "groq": [
        {"id": "openai/gpt-oss-20b",          "label": "GPT-OSS 20B",             "gratuit": True,  "recommande": True},
        {"id": "llama-3.3-70b-versatile",      "label": "Llama 3.3 70B Versatile", "gratuit": True,  "recommande": False},
        {"id": "llama-3.1-8b-instant",         "label": "Llama 3.1 8B Instant",    "gratuit": True,  "recommande": False},
        {"id": "llama3-70b-8192",              "label": "Llama 3 70B",             "gratuit": True,  "recommande": False},
        {"id": "llama3-8b-8192",               "label": "Llama 3 8B",              "gratuit": True,  "recommande": False},
        {"id": "mixtral-8x7b-32768",           "label": "Mixtral 8x7B",            "gratuit": True,  "recommande": False},
        {"id": "gemma2-9b-it",                 "label": "Gemma 2 9B",              "gratuit": True,  "recommande": False},
        {"id": "deepseek-r1-distill-llama-70b","label": "DeepSeek R1 70B",         "gratuit": True,  "recommande": False},
        {"id": "qwen-qwq-32b",                 "label": "Qwen QWQ 32B",            "gratuit": True,  "recommande": False},
    ],
    "anthropic": [
        {"id": "claude-sonnet-4-6",            "label": "Claude Sonnet 4.6",       "gratuit": False, "recommande": True},
        {"id": "claude-haiku-5-5",             "label": "Claude Haiku 5.5",        "gratuit": False, "recommande": False},
        {"id": "claude-opus-5-5",              "label": "Claude Opus 5.5",         "gratuit": False, "recommande": False},
        {"id": "claude-3-5-sonnet-20241022",   "label": "Claude 3.5 Sonnet",       "gratuit": False, "recommande": False},
        {"id": "claude-3-haiku-20240307",      "label": "Claude 3 Haiku",          "gratuit": False, "recommande": False},
    ],
    "openai": [
        {"id": "gpt-4o",                       "label": "GPT-4o",                  "gratuit": False, "recommande": True},
        {"id": "gpt-4o-mini",                  "label": "GPT-4o Mini",             "gratuit": False, "recommande": False},
        {"id": "gpt-4-turbo",                  "label": "GPT-4 Turbo",             "gratuit": False, "recommande": False},
        {"id": "gpt-3.5-turbo",                "label": "GPT-3.5 Turbo",           "gratuit": False, "recommande": False},
    ],
}

PROVIDERS_SUPPORTES = list(MODELES_DISPONIBLES.keys())


# ── Chiffrement Fernet (clé dérivée du JWT secret) ──────────────────────────

def _fernet() -> Any | None:
    """Retourne une instance Fernet ou None si cryptography n'est pas installé."""
    try:
        import base64
        import hashlib
        from cryptography.fernet import Fernet
        secret = os.getenv("SECRET_KEY", "forma-ia-default-secret-key-32chars!!")
        key = base64.urlsafe_b64encode(hashlib.sha256(secret.encode()).digest())
        return Fernet(key)
    except ImportError:
        logger.warning("⚠️ cryptography non installé — clés stockées en clair dans data/llm_config.json")
        return None


def _chiffrer(valeur: str) -> str:
    f = _fernet()
    if f:
        return f.encrypt(valeur.encode()).decode()
    return valeur


def _dechiffrer(valeur: str) -> str:
    f = _fernet()
    if f:
        try:
            return f.decrypt(valeur.encode()).decode()
        except Exception:
            return valeur  # déjà en clair (migration)
    return valeur


# ── Lecture / écriture ──────────────────────────────────────────────────────

def _lire_config() -> dict[str, Any]:
    if not _CONFIG_FILE.exists():
        return {}
    try:
        return json.loads(_CONFIG_FILE.read_text(encoding="utf-8"))
    except Exception as exc:
        logger.warning("⚠️ llm_config.json illisible : %s", exc)
        return {}


def _ecrire_config(data: dict[str, Any]) -> None:
    _CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
    _CONFIG_FILE.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


# ── API publique ────────────────────────────────────────────────────────────

def obtenir_config_active() -> dict[str, Any]:
    """Retourne la config LLM active (env + overrides fichier). Jamais de clé en clair."""
    cfg = _lire_config()
    provider = cfg.get("provider") or os.getenv("LLM_PROVIDER", "groq")
    model = cfg.get("model") or _modele_defaut_env(provider)
    return {
        "provider": provider,
        "model": model,
        "cle_groq_definie": bool(cfg.get("cle_groq") or os.getenv("GROQ_API_KEY", "").strip()),
        "cle_anthropic_definie": bool(cfg.get("cle_anthropic") or os.getenv("ANTHROPIC_API_KEY", "").strip()),
        "cle_openai_definie": bool(cfg.get("cle_openai") or os.getenv("OPENAI_API_KEY", "").strip()),
        "source": "fichier" if cfg else "env",
    }


def _modele_defaut_env(provider: str) -> str:
    if provider == "groq":
        return os.getenv("GROQ_MODEL", "openai/gpt-oss-20b")
    if provider == "anthropic":
        return os.getenv("ANTHROPIC_MODEL", "claude-3-5-sonnet-20241022")
    if provider == "openai":
        return os.getenv("OPENAI_MODEL", "gpt-4o")
    return ""


def appliquer_config(
    provider: str | None = None,
    model: str | None = None,
    cle_api: str | None = None,
) -> dict[str, Any]:
    """
    Met à jour la config LLM en runtime.
    - provider: "groq" | "anthropic" | "openai"
    - model: identifiant du modèle
    - cle_api: clé API pour le provider sélectionné (chiffrée avant stockage)

    Réinitialise le cache du LLM factory après modification.
    """
    cfg = _lire_config()

    if provider:
        if provider not in PROVIDERS_SUPPORTES:
            raise ValueError(f"Provider '{provider}' non supporté. Valeurs : {PROVIDERS_SUPPORTES}")
        cfg["provider"] = provider
        # Mettre à jour la variable d'environnement en mémoire
        os.environ["LLM_PROVIDER"] = provider

    if model:
        cfg["model"] = model
        provider_actif = cfg.get("provider", os.getenv("LLM_PROVIDER", "groq"))
        if provider_actif == "groq":
            os.environ["GROQ_MODEL"] = model
        elif provider_actif == "anthropic":
            os.environ["ANTHROPIC_MODEL"] = model
        elif provider_actif == "openai":
            os.environ["OPENAI_MODEL"] = model

    if cle_api and cle_api.strip():
        provider_actif = cfg.get("provider", os.getenv("LLM_PROVIDER", "groq"))
        cle_chiffree = _chiffrer(cle_api.strip())
        if provider_actif == "groq":
            cfg["cle_groq"] = cle_chiffree
            os.environ["GROQ_API_KEY"] = cle_api.strip()
        elif provider_actif == "anthropic":
            cfg["cle_anthropic"] = cle_chiffree
            os.environ["ANTHROPIC_API_KEY"] = cle_api.strip()
        elif provider_actif == "openai":
            cfg["cle_openai"] = cle_chiffree
            os.environ["OPENAI_API_KEY"] = cle_api.strip()

    _ecrire_config(cfg)

    # Réinitialiser le cache factory pour forcer le rechargement
    from app.services.llm.llm_factory import reset_providers_cache
    reset_providers_cache()

    logger.info("🔧 Config LLM mise à jour : provider=%s model=%s clé=%s",
                cfg.get("provider"), cfg.get("model"), "oui" if cle_api else "non")
    return obtenir_config_active()


def charger_cles_depuis_fichier() -> None:
    """
    Appelé au démarrage de l'application.
    Injecte les clés stockées dans data/llm_config.json dans os.environ
    pour qu'elles soient disponibles avant le premier appel LLM.
    """
    cfg = _lire_config()
    if not cfg:
        return

    if cfg.get("provider"):
        os.environ.setdefault("LLM_PROVIDER", cfg["provider"])
    if cfg.get("model"):
        provider = cfg.get("provider", "groq")
        if provider == "groq":
            os.environ.setdefault("GROQ_MODEL", cfg["model"])
        elif provider == "anthropic":
            os.environ.setdefault("ANTHROPIC_MODEL", cfg["model"])
        elif provider == "openai":
            os.environ.setdefault("OPENAI_MODEL", cfg["model"])

    if cfg.get("cle_groq"):
        os.environ.setdefault("GROQ_API_KEY", _dechiffrer(cfg["cle_groq"]))
    if cfg.get("cle_anthropic"):
        os.environ.setdefault("ANTHROPIC_API_KEY", _dechiffrer(cfg["cle_anthropic"]))
    if cfg.get("cle_openai"):
        os.environ.setdefault("OPENAI_API_KEY", _dechiffrer(cfg["cle_openai"]))

    logger.info("🔧 Config LLM chargée depuis data/llm_config.json (provider=%s)", cfg.get("provider"))


async def tester_connexion(provider: str, cle_api: str, model: str) -> dict[str, Any]:
    """Teste une clé API sans la sauvegarder."""
    if provider == "groq":
        try:
            from openai import AsyncOpenAI
            client = AsyncOpenAI(
                api_key=cle_api,
                base_url="https://api.groq.com/openai/v1",
            )
            resp = await client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": "Réponds juste: OK"}],
                max_tokens=5,
                temperature=0,
            )
            return {"ok": True, "message": f"Connexion réussie — {resp.model}"}
        except Exception as exc:
            return {"ok": False, "message": str(exc)}

    elif provider == "anthropic":
        try:
            import anthropic
            client = anthropic.AsyncAnthropic(api_key=cle_api)
            resp = await client.messages.create(
                model=model,
                max_tokens=5,
                messages=[{"role": "user", "content": "OK"}],
            )
            return {"ok": True, "message": f"Connexion réussie — {resp.model}"}
        except Exception as exc:
            return {"ok": False, "message": str(exc)}

    elif provider == "openai":
        try:
            from openai import AsyncOpenAI
            client = AsyncOpenAI(api_key=cle_api)
            resp = await client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": "OK"}],
                max_tokens=5,
                temperature=0,
            )
            return {"ok": True, "message": f"Connexion réussie — {resp.model}"}
        except Exception as exc:
            return {"ok": False, "message": str(exc)}

    return {"ok": False, "message": f"Provider '{provider}' non supporté pour le test."}
