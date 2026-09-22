"""
Tests de la Provider Abstraction (app/services/llm/).

Contexte : le paramètre json_mode de GroqProvider.generate() était déclaré
dans l'interface mais jamais implémenté (aucun response_format envoyé à
Groq). Ce comportement empêchait de migrer les services vers l'abstraction
sans perdre le mode JSON strict qu'ils utilisaient directement. Corrigé,
avec un filet de sécurité : l'API Groq exige le mot "json" dans les
messages quand response_format={"type": "json_object"} est utilisé
(sinon HTTP 400) — GroqProvider l'ajoute automatiquement si absent.

Aucun appel réseau : le client AsyncOpenAI est remplacé par un faux.

Exécution :
    python -m pytest tests/unit/test_llm_provider.py -q
"""

from types import SimpleNamespace

import pytest

from app.services.llm.groq_provider import GroqProvider
from app.services.llm.llm_provider import (
    LLMError,
    LLMInvalidResponseError,
    LLMNotAvailableError,
    LLMRateLimitError,
    LLMTimeoutError,
)
from app.services.llm import llm_factory


def run(coro):
    import asyncio
    return asyncio.run(coro)


@pytest.fixture(autouse=True)
def env(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "faux-token-de-test")
    monkeypatch.setenv("GROQ_MODEL", "openai/gpt-oss-20b")
    llm_factory.reset_providers_cache()
    yield
    llm_factory.reset_providers_cache()


class FauxClientGroq:
    """Remplace AsyncOpenAI : chat.completions.create(**kwargs)."""

    def __init__(self, reponse=None, erreur=None):
        self.reponse = reponse
        self.erreur = erreur
        self.derniers_kwargs = None

    async def _create(self, **kwargs):
        self.derniers_kwargs = kwargs
        if self.erreur:
            raise self.erreur
        message = SimpleNamespace(content=self.reponse or '{"ok": true}')
        usage = SimpleNamespace(prompt_tokens=10, completion_tokens=5, total_tokens=15)
        return SimpleNamespace(
            choices=[SimpleNamespace(message=message, finish_reason="stop")],
            usage=usage,
        )

    @property
    def chat(self):
        return SimpleNamespace(completions=SimpleNamespace(create=self._create))


@pytest.fixture
def provider():
    p = GroqProvider()
    p.client = FauxClientGroq()
    return p


# ============================================================
# json_mode — comportement corrigé
# ============================================================

def test_json_mode_true_envoie_response_format(provider):
    run(provider.generate("Rôle : agent.", "Analyse ceci. Réponds en json.",
                          json_mode=True))

    assert provider.client.derniers_kwargs["response_format"] == {"type": "json_object"}


def test_json_mode_false_n_envoie_pas_response_format(provider):
    run(provider.generate("Rôle.", "Tâche.", json_mode=False))

    assert "response_format" not in provider.client.derniers_kwargs


def test_mot_json_absent_le_filet_de_securite_l_ajoute(provider):
    run(provider.generate("Rôle.", "Analyse ce texte.", json_mode=True))

    envoye = provider.client.derniers_kwargs["messages"][1]["content"]
    assert "json" in envoye.lower()


def test_mot_json_deja_present_rien_n_est_ajoute(provider):
    user_prompt = "Réponds en JSON strict."
    run(provider.generate("Rôle.", user_prompt, json_mode=True))

    envoye = provider.client.derniers_kwargs["messages"][1]["content"]
    assert envoye == user_prompt          # inchangé, pas de suffixe dupliqué


def test_mot_json_dans_le_system_prompt_suffit(provider):
    """Le filet vérifie system+user combinés, pas seulement user_prompt."""
    run(provider.generate("Tu réponds toujours en JSON.", "Analyse ceci.",
                          json_mode=True))

    envoye = provider.client.derniers_kwargs["messages"][1]["content"]
    assert envoye == "Analyse ceci."      # pas touché : déjà couvert par le system


# ============================================================
# reasoning_effort — paramètre spécifique Groq (modèles de raisonnement)
# ============================================================

def test_reasoning_effort_transmis_si_fourni(provider):
    run(provider.generate("R", "U en json", reasoning_effort="low"))

    assert provider.client.derniers_kwargs["reasoning_effort"] == "low"


def test_reasoning_effort_absent_par_defaut(provider):
    run(provider.generate("R", "U en json"))

    assert "reasoning_effort" not in provider.client.derniers_kwargs


# ============================================================
# timeout — par appel (provider = singleton partagé)
# ============================================================

def test_timeout_transmis_si_fourni(provider):
    run(provider.generate("R", "U en json", timeout=15.0))

    assert provider.client.derniers_kwargs["timeout"] == 15.0


def test_timeout_absent_par_defaut(provider):
    run(provider.generate("R", "U en json"))

    assert "timeout" not in provider.client.derniers_kwargs


# ============================================================
# Réponse — forme du dict retourné
# ============================================================

def test_generate_retourne_le_contenu_et_les_metadonnees(provider):
    provider.client.reponse = '{"resultat": 42}'

    resultat = run(provider.generate("R", "U"))

    assert resultat["content"] == '{"resultat": 42}'
    assert resultat["finish_reason"] == "stop"
    assert resultat["provider"] == "groq"
    assert resultat["usage"]["total_tokens"] == 15


# ============================================================
# Erreurs — traduites en exceptions de l'abstraction
# ============================================================

def test_sans_cle_api_leve_not_available():
    import app.services.llm.groq_provider as mod
    p = mod.GroqProvider.__new__(mod.GroqProvider)
    p.api_key = ""
    p.client = None
    p.model = "x"

    with pytest.raises(LLMNotAvailableError):
        run(p.generate("R", "U"))


def test_timeout_devient_llm_timeout_error(provider):
    from openai import APITimeoutError
    provider.client.erreur = APITimeoutError(request=SimpleNamespace())

    with pytest.raises(LLMTimeoutError):
        run(provider.generate("R", "U"))


def test_rate_limit_devient_llm_rate_limit_error(provider):
    from openai import RateLimitError
    reponse = SimpleNamespace(status_code=429, headers={}, request=SimpleNamespace())
    provider.client.erreur = RateLimitError("quota", response=reponse, body=None)

    with pytest.raises(LLMRateLimitError):
        run(provider.generate("R", "U"))


# ============================================================
# generate_with_retry (méthode concrète héritée)
# ============================================================

def test_retry_reussit_apres_un_echec_transitoire(provider, monkeypatch):
    appels = {"n": 0}
    reponse_ok = SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content="ok"),
                                 finish_reason="stop")],
        usage=SimpleNamespace(prompt_tokens=1, completion_tokens=1, total_tokens=2),
    )

    async def create(**kwargs):
        appels["n"] += 1
        if appels["n"] == 1:
            from openai import APITimeoutError
            raise APITimeoutError(request=SimpleNamespace())
        return reponse_ok

    provider.client._create = create

    async def sommeil_instantane(*_):
        return None

    monkeypatch.setattr("asyncio.sleep", sommeil_instantane)  # pas d'attente réelle

    resultat = run(provider.generate_with_retry("R", "U", max_retries=3))

    assert appels["n"] == 2 and resultat["content"] == "ok"


def test_erreur_non_transitoire_pas_de_retry(provider):
    provider.client.erreur = ValueError("erreur définitive")

    with pytest.raises(LLMError):
        run(provider.generate_with_retry("R", "U", max_retries=3))

    assert provider.client.derniers_kwargs is not None  # un seul appel tenté


# ============================================================
# Factory — sélection du provider
# ============================================================

def test_factory_retourne_groq_par_defaut(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "groq")

    provider = llm_factory.get_llm_provider()

    assert provider.get_provider_name() == "groq"


def test_factory_provider_inconnu_leve_not_available():
    with pytest.raises(LLMNotAvailableError):
        llm_factory.get_llm_provider(force_provider="inexistant")


def test_factory_met_en_cache_la_meme_instance():
    a = llm_factory.get_llm_provider(force_provider="groq")
    b = llm_factory.get_llm_provider(force_provider="groq")

    assert a is b
