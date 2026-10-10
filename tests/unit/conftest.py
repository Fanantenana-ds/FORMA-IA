# tests/unit/conftest.py
# ============================================================
# Configuration partagée pour les tests unitaires IA
# ============================================================
# Les tests unitaires créent leurs propres mini-apps FastAPI locales
# avec app.include_router(router_ia, ...). Ces routers ont
# dependencies=[Depends(verify_api_key)].
# FastAPI capture la référence à verify_api_key à l'import du router —
# on ne peut pas la changer après coup via monkeypatch du module.
# Solution : patcher FastAPI.include_router pour qu'il injecte
# automatiquement dependency_overrides sur chaque app de test.
# ============================================================

import os

_TEST_TOKEN = "test-shared-token-unitaire"
os.environ["SHARED_INTERNAL_TOKEN"] = _TEST_TOKEN
os.environ["IA_API_KEY"] = _TEST_TOKEN

import pytest
from fastapi import FastAPI as _FastAPI
from app.utils.security import verify_api_key as _verify_api_key

_orig_include_router = _FastAPI.include_router


async def _noop():
    return None


def _include_router_with_override(self, router, **kwargs):
    _orig_include_router(self, router, **kwargs)
    self.dependency_overrides[_verify_api_key] = _noop


# Patch immédiat sur la classe FastAPI — affecte toutes les instances créées
# dans ce processus de test, y compris celles créées dans les fixtures
_FastAPI.include_router = _include_router_with_override


# ============================================================
# FauxLLM — fixture partagée pour tous les tests unitaires IA
# ============================================================
import json as _json
import pytest


class FauxLLM:
    """
    Faux LLMProvider (interface app.services.llm.LLMProvider.generate).
    Paramètres :
      contenu  — str ou dict renvoyé comme contenu JSON
      finish   — finish_reason (défaut : "stop")
      erreur   — exception à lever si fournie
    """
    def __init__(self, contenu=None, finish="stop", erreur=None):
        self.contenu = contenu
        self.finish = finish
        self.erreur = erreur
        self.appels = 0

    async def generate(self, system_prompt, user_prompt, temperature=0.4,
                       max_tokens=4000, json_mode=True, **kwargs):
        self.appels += 1
        if self.erreur:
            raise self.erreur
        contenu = self.contenu if isinstance(self.contenu, str) else _json.dumps(self.contenu)
        return {"content": contenu, "finish_reason": self.finish,
                "usage": {}, "model": "faux", "provider": "faux"}

    async def generate_with_retry(self, *args, **kwargs):
        return await self.generate(*args, **kwargs)


@pytest.fixture
def faux_llm():
    """Fixture FauxLLM vide — configurer .contenu et .erreur selon le test."""
    return FauxLLM()
