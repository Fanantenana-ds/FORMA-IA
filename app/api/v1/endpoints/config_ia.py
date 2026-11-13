# app/api/v1/endpoints/config_ia.py
# ============================================================
# ROUTES IA — Configuration LLM en runtime
# ============================================================
# GET  /ia/config/llm                  → config active (sans clés)
# POST /ia/config/llm                  → modifier provider/modèle/clé
# GET  /ia/config/llm/models/{provider}→ modèles disponibles
# POST /ia/config/llm/tester           → tester une clé sans sauvegarder
# GET  /ia/config/llm/health           → santé
# ============================================================

import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.core.dependencies import get_current_user
from app.services.llm.llm_config_service import (
    MODELES_DISPONIBLES,
    PROVIDERS_SUPPORTES,
    appliquer_config,
    obtenir_config_active,
    tester_connexion,
)

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/ia/config",
    tags=["Config — Configuration LLM runtime"],
    dependencies=[Depends(get_current_user)],
)


# ── Schémas ─────────────────────────────────────────────────────────────────

class ConfigLLMUpdate(BaseModel):
    provider: str | None = Field(None, description="groq | anthropic | openai")
    model: str | None = Field(None, description="Identifiant du modèle")
    cle_api: str | None = Field(None, description="Clé API (chiffrée avant stockage, jamais retournée)")


class TestConnexionRequest(BaseModel):
    provider: str = Field(..., description="groq | anthropic | openai")
    cle_api: str = Field(..., min_length=10, description="Clé API à tester")
    model: str = Field(..., description="Modèle à utiliser pour le test")


# ── Routes ──────────────────────────────────────────────────────────────────

@router.get("/llm", summary="Configuration LLM active")
async def get_config_llm():
    """Retourne la configuration LLM active. Les clés API ne sont jamais retournées."""
    return obtenir_config_active()


@router.post("/llm", summary="Modifier la configuration LLM")
async def post_config_llm(body: ConfigLLMUpdate, principal=Depends(get_current_user)):
    """
    Met à jour provider, modèle et/ou clé API en runtime.
    Aucun redémarrage nécessaire. La nouvelle config est appliquée immédiatement.
    """
    role = getattr(principal, "role", None)
    role_str = role.value if hasattr(role, "value") else str(role or "")
    if role_str.upper() not in ("DIRECTION", "ADMIN"):
        raise HTTPException(status_code=403, detail="Seuls les rôles DIRECTION et ADMIN peuvent modifier la configuration LLM.")

    if not body.provider and not body.model and not body.cle_api:
        raise HTTPException(status_code=400, detail="Au moins un champ doit être fourni (provider, model ou cle_api).")

    try:
        config = appliquer_config(
            provider=body.provider,
            model=body.model,
            cle_api=body.cle_api,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    logger.info("🔧 Config LLM modifiée par %s", getattr(principal, "email", "?"))
    return {"message": "Configuration appliquée avec succès.", "config": config}


@router.get("/llm/models/{provider}", summary="Modèles disponibles pour un provider")
async def get_models(provider: str):
    """Retourne la liste des modèles disponibles pour un provider donné."""
    provider = provider.lower().strip()
    if provider not in MODELES_DISPONIBLES:
        raise HTTPException(
            status_code=404,
            detail=f"Provider '{provider}' inconnu. Disponibles : {PROVIDERS_SUPPORTES}",
        )
    return {
        "provider": provider,
        "models": MODELES_DISPONIBLES[provider],
    }


@router.get("/llm/models", summary="Tous les providers et leurs modèles")
async def get_all_models():
    """Retourne tous les providers avec leurs modèles disponibles."""
    return {
        "providers": PROVIDERS_SUPPORTES,
        "models": MODELES_DISPONIBLES,
    }


@router.post("/llm/tester", summary="Tester une clé API sans la sauvegarder")
async def test_connexion(body: TestConnexionRequest, principal=Depends(get_current_user)):
    """
    Teste une clé API en effectuant un appel minimal.
    La clé n'est pas sauvegardée.
    """
    role = getattr(principal, "role", None)
    role_str = role.value if hasattr(role, "value") else str(role or "")
    if role_str.upper() not in ("DIRECTION", "ADMIN"):
        raise HTTPException(status_code=403, detail="Seuls les rôles DIRECTION et ADMIN peuvent tester les clés API.")

    result = await tester_connexion(
        provider=body.provider,
        cle_api=body.cle_api,
        model=body.model,
    )
    return result


@router.get("/llm/health", summary="Santé du service de configuration LLM")
async def health():
    try:
        config = obtenir_config_active()
        return {"status": "ok", "provider": config["provider"], "model": config["model"]}
    except Exception as exc:
        return {"status": "erreur", "detail": str(exc)}
